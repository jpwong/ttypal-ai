import tempfile
from pathlib import Path

from ttypal.logger import Logger


def test_logger_creates_file(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path), rotate_size_kb=1)
    logger.write(b"hello world\n")
    logger.close()

    log_files = list((tmp_path / "testboard").glob("*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text()
    assert "hello world" in content


def test_logger_adds_timestamp(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path),
                    timestamp_format="%H:%M:%S")
    logger.write(b"line1\n")
    logger.close()

    content = (tmp_path / "testboard").glob("*.log").__next__().read_text()
    # timestamp format: [HH:MM:SS]
    assert content.startswith("[")
    assert "] line1\n" in content


def test_logger_rotation(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path), rotate_size_kb=1)
    # Write more than 1KB to trigger rotation
    for i in range(200):
        logger.write(f"{'x' * 100}\n".encode())
    logger.close()

    log_files = list((tmp_path / "testboard").glob("*.log"))
    assert len(log_files) > 1


def test_logger_multiline(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path),
                    timestamp_format="%S")
    logger.write(b"a\nb\nc\n")
    logger.close()

    content = (tmp_path / "testboard").glob("*.log").__next__().read_text()
    lines = content.strip().split("\n")
    assert len(lines) == 3
    for line in lines:
        assert line.startswith("[")
