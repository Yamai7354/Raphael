Epic: Layer 2 – Perception

Objective: Process raw signals from the Environment Layer, normalize them across formats, and utilize specific models (Vision, Speech, Text) combined with attention mechanisms to provide structured context for the OS.

Jira Tickets

1. Input Normalizer

Description: Implement an Input Normalizer to standardize formats, timestamps, and units coming from the Environment Layer.

Acceptance Criteria:

Raw data (metrics, logs, strings) are formatted uniformly.
Timestamps and units match a unified system standard.

Subtasks:

PER-1: Implement Input Normalizer to standardize formats, timestamps, and units.

2. Modality Models Integration (Vision, Speech, Text)

Description: Integrate dedicated perception models for vision (Moondream), speech (Whisper), and deep text understanding (tokenization, parsing, entity recognition).

Acceptance Criteria:

Images/Video inputs are processed by Moondream.
Audio inputs are transcribed and processed by Whisper.
Text inputs are tokenized and pre-parsed for entities and intent.

Subtasks:

PER-2: Integrate Vision models (Moondream) for object detection and scene understanding.
PER-3: Integrate Speech models (Whisper) for audio-to-text conversion and semantic extraction.
PER-4: Implement Text Understanding: tokenization, parsing, entity recognition, intent detection.

3. Attention, Synchronization & Filtering

Description: Design an Attention Mechanism capable of priority filtering across multi-modal signals, utilizing timestamps and embeddings for perfect synchronization.

Acceptance Criteria:

High-priority signals (e.g., explicit user commands) bypass low-priority noise (e.g., background telemetry).
Vision, audio, and text related to the same event are synced temporally.

Subtasks:

PER-5: Design Attention / Priority Filtering mechanism for signals from Vision, Speech, and Text.
PER-7: Ensure multi-modal synchronization (vision/audio/text) using timestamps and embeddings.

4. Event Bus Connection & Downstream Routing

Description: Connect the filtered outputs from the Attention mechanisms directly to the System Event Bus for downstream processing.

Acceptance Criteria:

Filtered, normalized, and model-processed events arrive correctly on the System Event Bus.

Subtasks:

PER-6: Connect Attention outputs to the System Event Bus for downstream consumption.

5. Validation & Documentation

Description: Test perception outputs with simulated inputs to validate accuracy, and comprehensively document the perception interfaces and event structures.

Acceptance Criteria:

Test suite passes against mocked multi-modal inputs.
Documentation effectively enables developers to route new data types through the Perception Layer.

Subtasks:

PER-8: Test perception outputs with simulated inputs to validate accuracy and attention prioritization.
PER-9: Document perception interfaces, data formats, and event structures for other layers.
