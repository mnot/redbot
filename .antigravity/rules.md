# Project Rules

You are writing a Python application for linting HTTP resources. Adherence to the relevant standard specifications is paramount; avoid relying on sources like MDN unless the standard is ambiguous or out of date. Always refer to the most current version of each standard.


## Code Style

- PEP8 style Python with 100 charcter line lengths.

- All code should have type declarations.

- All code additions and changes should have tests, using existing infrastructure where possible. Tests shoudl reside in the same file as the code unless it is used in multiple files, in which case it should be separate. New test files in `test/` should be added as a target in the Makefile and invoked by `make test`.

## Workflow

For each code change:

1. Typecheck by running `make typecheck`
2. Lint by running `make lint`
3. Test by running `make test`
4. Format by running `make tidy` (this can fix line length issues and trailing whitespace)

If you need to run a Python interpreter, use `make python` or the python in `.venv/`. Note that `make` targets automatically use the virtual environment, so you don't need to activate it explicitly.

You can run REDbot as a web service with `make server`. 

