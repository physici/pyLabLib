del /Q build
del /Q dist
python setup.py sdist
python setup.py bdist_wheel
REM twine upload dist/*
twine upload --repository testpypi dist/*