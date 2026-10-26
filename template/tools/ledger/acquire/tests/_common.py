"""Shared set-up of the acquire tests: paths, a temporary project root per test, and a network guard (every test module blocks
sockets for its whole run, so a test that reached the network fails instead of passing quietly)."""
import hashlib, os, shutil, socket, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
if HERE not in sys.path: sys.path.insert(0, HERE)
FIXTURES = os.path.join(TOOLS, "ledger", "tests")      # casebook_corpus.py: the synthetic corpus the tests run on (phase 7a)
if FIXTURES not in sys.path: sys.path.insert(0, FIXTURES)

_saved = {}
_VISION = os.path.join(ROOT, ".ledger", "bin", "ocr_vision")
if os.path.isfile(_VISION) and not os.environ.get("LEDGER_OCR_VISION_BIN"):
    os.environ["LEDGER_OCR_VISION_BIN"] = _VISION     # the project's built Vision tool (ocr.py --compile), so tests do not rebuild it


def has_ocr():
    """A renderer and an OCR backend that can run without compiling: the second-witness tests run only then."""
    from ledger.acquire import ocr as O
    return O.renderer() is not None and O.backend(ROOT)[0] in ("vision", "tesseract")


class NetworkRefused(ConnectionError):
    pass


def block_network():
    if _saved: return
    def refuse(*a, **k): raise NetworkRefused("network refused in the acquire tests")
    _saved.update(connect=socket.socket.connect, create_connection=socket.create_connection, connect_ex=socket.socket.connect_ex)
    socket.socket.connect = refuse; socket.socket.connect_ex = refuse; socket.create_connection = refuse


def allow_network():
    if not _saved: return
    socket.socket.connect = _saved["connect"]; socket.socket.connect_ex = _saved["connect_ex"]; socket.create_connection = _saved["create_connection"]
    _saved.clear()


def temp_root(test):
    """A temporary project root removed after the test; holds a minimal ledger.toml so nothing resolves to the real project."""
    d = tempfile.mkdtemp(prefix="ledger-acquire-test-")
    with open(os.path.join(d, "ledger.toml"), "w", encoding="utf-8", newline="\n") as f: f.write('[ledger]\nname = "acquire-test"\n')
    test.addCleanup(shutil.rmtree, d, True)
    return d


def sha(path):
    with open(path, "rb") as f: return hashlib.sha256(f.read()).hexdigest()
