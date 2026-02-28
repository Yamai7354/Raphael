import requests
import json
import time

# =============================================================================
# OPTION 1: Using the OpenAI Client (Recommended for compatibility)
# =============================================================================
try:
    from openai import OpenAI

    # Point client to our Router
    client = OpenAI(base_url="http://localhost:9000/v1", api_key="sk-not-required-for-local-router")

    print("\n--- [1] OpenAI Client Test ---")
    response = client.chat.completions.create(
        model="any",  # Router ignores this if 'role' is provided, or picks best general model
        messages=[{"role": "user", "content": "Explain quantum entanglement briefly."}],
        extra_body={"role": "chat"},  # HINT: Tell router we want a 'chat' specialist
    )
    print(f"Response: {response.choices[0].message.content}")

except ImportError:
    print("OpenAI library not installed. Skipping Option 1.")


# =============================================================================
# OPTION 2: Using the Raw Task API (Recommended for complex workflows)
# =============================================================================
print("\n--- [2] Raw Task API Test ---")

ROUTER_URL = "http://localhost:9000"

# 1. Submit a complex task
task_payload = {
    "task_id": f"example-task-{int(time.time())}",
    "objective": "Write a Python script to calculate Fibonacci numbers and explain it.",
    "constraints": ["efficient_code", "clear_comments"],
}

print(f"Submitting task: {task_payload['task_id']}...")
resp = requests.post(f"{ROUTER_URL}/task/create", json=task_payload)
if resp.status_code == 200:
    data = resp.json()
    print(f"Task Created! Plan Hash: {data.get('plan_hash')}")
    print(f"Subtasks Generated: {len(data.get('subtasks', []))}")
else:
    print(f"Error: {resp.text}")

# 2. Poll for status (Simulated)
print("Task check link: http://localhost:9000/task/" + task_payload["task_id"] + "/status")
