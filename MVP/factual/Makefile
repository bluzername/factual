.PHONY: setup test clean lint format help

help:
	@echo "Factual Pipeline - Automated Instagram Reels Fact-Checking"
	@echo ""
	@echo "Usage:"
	@echo "  make setup    - Set up the environment (create directories, sample watermark)"
	@echo "  make test     - Run the test suite"
	@echo "  make lint     - Run ruff and a byte-compile check"
	@echo "  make format   - Format code with ruff"
	@echo "  make clean    - Remove temporary files and directories"

setup:
	python setup.py

test:
	python -m pytest .

lint:
	ruff check .
	python -m compileall -q .

format:
	ruff format .

clean:
	rm -rf temp/* output/*
	rm -f *.pyc
	rm -rf __pycache__ 