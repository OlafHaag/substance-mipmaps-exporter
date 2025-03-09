# Copilot instructions

## Python instructions

We use Python 3.11, so when your responses include Python code, please use Python 3.11 features and syntax.
We always write Python in PEP8 compatible style with a line width of 120 characters, so when your responses include Python code, please follow those conventions.
We always write Python with double quotes and spaces for indentation, so when your responses include Python code, please follow those conventions.
Our Python doc-strings should be formatted according to PEP 257 conventions, using `:param` for parameters and `:return` for return values.
The first line of a docstring should be in imperative mood.
All new code must include proper type hints for better readability and maintainability.
Follow SOLID principles when writing code.
Most important are the Single Responsibility Principle and the Dependency Inversion Principle.
Use dependency injection to inject dependencies into classes and functions, when appropriate.

We use the Adobe Substance 3D Designer 14 Python API, so when your responses include Adobe Substance 3D Designer code, please use the Adobe Substance 3D Designer 14 API.

When commenting on code, comments should explain the "why" rather than the "what", and should be complete sentences ending in a period.

### Tests

When you change code, you must also change the tests to ensure that the code works as expected.
When you add new code, you must also add tests to ensure that the new code works as expected.
When you fix bugs, you must also add tests to ensure that the bug is fixed and does not reoccur.
When you refactor code, you must also change the tests to ensure that the refactored code works as expected.
When you write tests, please follow the following guidelines:
When writing tests for Python code, please use `pytest` as the testing framework and follow the pytest conventions.
Follow the arrange, act, assert pattern for structuring tests.
Structure tests for members of classes under a test class named after the class being tested.
Structure tests for the same function under a test class named after the function being tested.
Use `pytest.mark.parametrize` for parameterized tests and `pytest.fixture` for fixtures.
Add ids to parameterized tests that add short and precise titles for what each set of inputs is testing, for better readability.
Use `assert` statements for assertions.
Use `pytest.raises` for testing exceptions. Use `pytest.skip` for skipping tests.
Use `pytest.mark.asyncio` for async tests.
Use mocks to simulate or patch dependencies to function calls or classes that use dependency injections, and verify that a mocked function is called correctly.
Develop a comprehensive suite of unit tests for the functions and classes you are ordered to do in Python.
Write multiple test methods that cover a wide range of scenarios, including edge cases, exception handling, and data validation.
