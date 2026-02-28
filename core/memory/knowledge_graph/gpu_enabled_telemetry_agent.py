# swarm_telemetry_agent_gpu.py
# Telemetry agent with GPU monitoring

import os
import time
import socket
import psutil
import subprocess
import requests
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

NODE_ID = socket.gethostname()
OLLAMA_URL = "http://100.125.58.22:5000"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def get_cpu_ram():
    return {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent}


def get_gpu_stats():
    gpus = []
    # Try NVIDIA
    try:
        result = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
            .split("\n")
        )

        for gpu in result:
            if not gpu.strip():
                continue
            name, util, mem_used, mem_total, temp, power = gpu.split(", ")
            gpus.append(
                {
                    "name": name.strip(),
                    "util": int(util),
                    "mem_used": int(mem_used),
                    "mem_total": int(mem_total),
                    "temp": int(temp),
                    "power": float(power),
                }
            )
    except:
        pass

    # Try AMD
    try:
        # Basic parsing for rocm-smi output
        # rocm-smi --showuse --showmeminfo vram
        output = subprocess.check_output(
            ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"], stderr=subprocess.DEVNULL
        ).decode()
        import json

        data = json.loads(output)
        # rocm-smi --json output structure varies, but usually it's a dict per card
        for card_id, stats in data.items():
            if not card_id.startswith("card"):
                continue
            gpus.append(
                {
                    "name": f"AMD GPU {card_id}",
                    "util": int(stats.get("GPU use (%)", 0)),
                    "mem_used": int(stats.get("VRAM Total Used (B)", 0)) // (1024**2),
                    "mem_total": int(stats.get("VRAM Total Memory (B)", 0)) // (1024**2),
                    "temp": int(stats.get("Temperature (Sensor edge) (C)", 0)),
                    "power": float(stats.get("Average Graphics Package Power (W)", 0)),
                }
            )
    except:
        pass

    return gpus


def get_models():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.json().get("models", [])
    except:
        return []


def update_graph(cpu_ram, gpus, models):
    with driver.session() as session:
        session.run(
            """
        MERGE (m:Machine {id:$node})
        SET m.cpu_usage = $cpu,
            m.ram_usage = $ram,
            m.last_seen = timestamp()
        """,
            node=NODE_ID,
            cpu=cpu_ram["cpu"],
            ram=cpu_ram["ram"],
        )

        for gpu in gpus:
            session.run(
                """
            MERGE (g:Hardware {name:$name})
            SET g.type = "GPU",
                g.utilization = $util,
                g.vram_used = $mem_used,
                g.vram_total = $mem_total,
                g.temperature = $temp,
                g.power_draw = $power
            WITH g
            MATCH (m:Machine {id:$node})
            MERGE (m)-[:HAS_HARDWARE]->(g)
            """,
                node=NODE_ID,
                name=gpu["name"],
                util=gpu["util"],
                mem_used=gpu["mem_used"],
                mem_total=gpu["mem_total"],
                temp=gpu["temp"],
                power=gpu["power"],
            )

        for model in models:
            session.run(
                """
            MERGE (mod:Model {name:$model})
            WITH mod
            MATCH (mach:Machine {id:$node})
            MERGE (mod)-[:RUNS_ON]->(mach)
            """,
                model=model["name"],
                node=NODE_ID,
            )


def main():
    print(f"Starting GPU-enabled telemetry for node: {NODE_ID}")
    while True:
        try:
            cpu_ram = get_cpu_ram()
            gpus = get_gpu_stats()
            models = get_models()
            update_graph(cpu_ram, gpus, models)
        except Exception as e:
            print(f"Telemetry error: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()
