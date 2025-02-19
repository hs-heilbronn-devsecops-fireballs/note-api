import os
from fastapi import FastAPI, Depends
from uuid import uuid4
from typing import List, Optional
from typing_extensions import Annotated
from starlette.responses import RedirectResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.resources import Resource
from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend
from .model import Note, CreateNoteRequest

# Initialize OpenTelemetry Tracer provider and exporter
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create({"service.name": "note-api"})
    )
)
tracer_provider = trace.get_tracer_provider()
cloud_exporter = CloudTraceSpanExporter()
span_processor = BatchSpanProcessor(cloud_exporter)
tracer_provider.add_span_processor(span_processor)

# Create the FastAPI app
app = FastAPI()

# Instrument FastAPI app
FastAPIInstrumentor.instrument_app(app)

my_backend: Optional[Backend] = None

def get_backend() -> Backend:
    global my_backend
    if my_backend is None:
        backend_type = os.getenv('BACKEND', 'memory')
        if backend_type == 'redis':
            my_backend = RedisBackend()
        elif backend_type == 'gcs':
            my_backend = GCSBackend()
        else:
            my_backend = MemoryBackend()
    return my_backend

@app.get('/')
def redirect_to_notes() -> None:
    return RedirectResponse(url='/notes')

@app.get('/notes')
def get_notes(backend: Annotated[Backend, Depends(get_backend)]) -> List[Note]:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_notes_span"):
        # Custom span for fetching keys
        with tracer.start_as_current_span("fetch_keys_span"):
            keys = backend.keys()
        
        # Custom span for retrieving notes from the backend
        with tracer.start_as_current_span("fetch_notes_span"):
            notes = [backend.get(key) for key in keys]
        
        return notes

@app.get('/notes/{note_id}')
def get_note(note_id: str, backend: Annotated[Backend, Depends(get_backend)]) -> Note:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_note_span"):
        # Custom span for fetching a specific note
        note = backend.get(note_id)
        return note

@app.put('/notes/{note_id}')
def update_note(note_id: str, request: CreateNoteRequest, backend: Annotated[Backend, Depends(get_backend)]) -> None:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("update_note_span"):
        # Custom span for updating a note
        backend.set(note_id, request)

@app.post('/notes')
def create_note(request: CreateNoteRequest, backend: Annotated[Backend, Depends(get_backend)]) -> str:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("create_note_span"):
        # Custom span for creating a note
        note_id = str(uuid4())
        backend.set(note_id, request)
        return note_id
