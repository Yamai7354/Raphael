from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter


def setup_telemetry():
    """
    Initializes OpenTelemetry tracing for the Swarm Director.
    This allows monitoring the lifecycle of Tasks -> Environments -> Pods -> LLM Calls.
    """
    # Create the provider
    provider = TracerProvider()

    # In production, use OTLPSpanExporter to send to Loki/Jaeger/Prometheus
    # For now, we will simply log spans to the console
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)

    # Sets the global default tracer provider
    trace.set_tracer_provider(provider)

    # Example of getting a tracer
    # tracer = trace.get_tracer("swarm.director")
    # with tracer.start_as_current_span("MySwarmTask"):
    #     do_something()
