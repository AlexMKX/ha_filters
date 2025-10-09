#!/bin/bash
set -e

echo "====== Running unit tests ======"
python -m pytest tests/test_auto_area_assign.py -v

echo ""
echo "====== Running e2e tests ======"
python -m pytest tests/test_e2e_auto_area_assign.py -v

echo ""
echo "✅ All tests passed!"

