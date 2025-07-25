import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Minimal stubs for heavy dependencies
if "torch" not in sys.modules:
    torch_stub = ModuleType("torch")
    torch_stub.cuda = SimpleNamespace(is_available=lambda: False)
    sys.modules["torch"] = torch_stub

if "numpy" not in sys.modules:
    numpy_stub = ModuleType("numpy")
    numpy_stub.dot = lambda a, b: 0.0
    sys.modules["numpy"] = numpy_stub

for mod_name in ["faiss", "sentence_transformers", "transformers", "peft", "gradio"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = ModuleType(mod_name)

# faiss helpers used in code
sys.modules["faiss"].read_index = lambda *a, **k: None
sys.modules["faiss"].get_num_gpus = lambda: 0


class DummyStandardGpuResources:
    def __init__(self, *a, **k):
        pass


sys.modules["faiss"].StandardGpuResources = DummyStandardGpuResources
sys.modules["faiss"].index_cpu_to_gpu = lambda res, device, index: index

sys.modules["sentence_transformers"].CrossEncoder = object
sys.modules["sentence_transformers"].SentenceTransformer = object

sys.modules["transformers"].AutoModelForCausalLM = object
sys.modules["transformers"].AutoTokenizer = object
sys.modules["transformers"].BitsAndBytesConfig = object
sys.modules["transformers"].TextIteratorStreamer = object
sys.modules["transformers"].pipeline = lambda *a, **k: None

sys.modules["peft"].PeftModel = object


# minimal gradio Blocks class for build_demo
class DummyBlocks:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def launch(self, *a, **k):
        pass

    def close(self):
        pass

    def queue(self, *a, **k):
        return self


class DummyComponent:
    def __init__(self, *a, **k):
        pass

    def submit(self, *a, **k):
        return self

    def then(self, *a, **k):
        return self


sys.modules["gradio"].Blocks = DummyBlocks
sys.modules["gradio"].themes = SimpleNamespace(Soft=lambda: None)
sys.modules["gradio"].Markdown = lambda *a, **k: None
sys.modules["gradio"].State = lambda *a, **k: None
sys.modules["gradio"].Chatbot = DummyComponent
sys.modules["gradio"].Textbox = DummyComponent
