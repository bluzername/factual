.PHONY: setup test clean lint format help

help:
	@echo "Factual Pipeline - Automated Instagram Reels Fact-Checking"
	@echo ""
	@echo "Usage:"
	@echo "  make setup    - Set up the environment (create directories, sample watermark)"
	@echo "  make test     - Run the test suite"
	@echo "  make lint     - Run linters (flake8, mypy)"
	@echo "  make format   - Format code (black, isort)"
	@echo "  make clean    - Remove temporary files and directories"

setup:
	python setup.py

test:
	pytest -xvs test_pipeline.py

lint:
	flake8 factual_pipeline.py test_pipeline.py setup.py
	mypy factual_pipeline.py test_pipeline.py setup.py

format:
	black factual_pipeline.py test_pipeline.py setup.py
	isort factual_pipeline.py test_pipeline.py setup.py

clean:
	rm -rf temp/* output/*
	rm -f *.pyc
	rm -rf __pycache__ 