import logging
import os
from time import strftime

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - [%(levelname)s] - %(message)s"
)

console_formatter = logging.Formatter(
    "\033[92m%(asctime)s - %(name)s:%(levelname)s\033[0m: %(filename)s:%(lineno)s - %(message)s",
    datefmt="%H:%M:%S",
)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s:%(levelname)s: %(filename)s:%(lineno)s - %(message)s",
    datefmt="%H:%M:%S",
)

def get_console_handler():
    """
    Returns a console handler for logging.
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    return console_handler

def get_file_handler():
    """
    Returns a file handler for logging.
    """
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, "opendevin.log"))
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    return file_handler

opendevin_logger = logging.getLogger("opendevin")
opendevin_logger.setLevel(logging.DEBUG)
opendevin_logger.propagate = False
opendevin_logger.addHandler(get_console_handler())
opendevin_logger.addHandler(get_file_handler())

class LlmFileHandler(logging.FileHandler):

    def __init__(self, filename, mode='a', encoding=None, delay=False):
        """
        Initializes an instance of LlmFileHandler.

        Args:
            filename (str): The name of the log file.
            mode (str, optional): The file mode. Defaults to 'a'.
            encoding (str, optional): The file encoding. Defaults to None.
            delay (bool, optional): Whether to delay file opening. Defaults to False.
        """
        self.filename = filename
        self.message_counter = 0
        self.session = strftime("%y-%m-%d_%H-%M-%S")
        self.log_directory = os.path.join(os.getcwd(), "logs", "llm", self.session)
        os.makedirs(self.log_directory, exist_ok=True)
        self.baseFilename = os.path.join(self.log_directory, f"{self.filename}_{self.message_counter:03}.log")
        super().__init__(self.baseFilename, mode, encoding, delay)

    def emit(self, record):
        """
        Emits a log record.

        Args:
            record (logging.LogRecord): The log record to emit.
        """
        self.baseFilename = os.path.join(self.log_directory, f"{self.filename}_{self.message_counter:03}.log")
        self.stream = self._open()
        super().emit(record)
        self.stream.close
        self.message_counter += 1

def get_llm_prompt_file_handler():
    """
    Returns a file handler for LLM prompt logging.
    """
    llm_prompt_file_handler = LlmFileHandler("prompt")
    llm_prompt_file_handler.setLevel(logging.DEBUG)
    llm_prompt_file_handler.setFormatter(file_formatter)
    return llm_prompt_file_handler

def get_llm_response_file_handler():
    """
    Returns a file handler for LLM response logging.
    """
    llm_response_file_handler = LlmFileHandler("response")
    llm_response_file_handler.setLevel(logging.DEBUG)
    llm_response_file_handler.setFormatter(file_formatter)
    return llm_response_file_handler

llm_prompt_logger = logging.getLogger("prompt")
llm_prompt_logger.setLevel(logging.DEBUG)
llm_prompt_logger.propagate = False
llm_prompt_logger.addHandler(get_llm_prompt_file_handler())

llm_response_logger = logging.getLogger("response")
llm_response_logger.setLevel(logging.DEBUG)
llm_response_logger.propagate = False
llm_response_logger.addHandler(get_llm_response_file_handler())
