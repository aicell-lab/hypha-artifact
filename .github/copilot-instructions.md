Follow this coding style for Python code, and equivalent rules for other languages:
1. Write short functions
- Try to keep functions under 20 lines. Even one-liners are preferable when possible.
2. Use descriptive names for variables and functions
- Don't be afraid of long names if they improve clarity. Never use abbreviations unless they are very common and well-known.
- Never ever use single-letter variable names.
3. Add docstrings to functions.
- Public API functions, and always those decorated with @schema_function or @schema_method should have extensive docstrings explaining their purpose, parameters, and return values.
- Smaller helper functions should have brief docstrings.
4. Use type hints for function parameters and return types.
- Avoid using 'Any' type hints; be as specific as possible.
- When 'Any' seems necessary, try using 'object' instead.
- Use modern typing constructs like 'list[int]' instead of 'List[int]', 'dict[str, str]' instead of 'Dict[str, str]', 'A | B' instead of 'Union[A, B]', etc.
- For parameters, be generic. E.g. use 'Sequence' instead of 'list' and 'Mapping' instead of 'dict'.
- For return types, be specific. E.g. use 'list' or 'dict' when applicable.
- Prefer using 'Literal' for fixed values and 'TypedDict' for structured data.
- For generic types, use TypeVar with appropriate constraints.
- Use from __future__ import annotations for forward references in type hints.
- There should ALWAYS be a return type hint, even if it's None.
5. @schema_function and @schema_method decorators:
- Ensure that functions decorated with @schema_function or @schema_method have detailed docstrings explaining their purpose, parameters, and return values.
- Use pydantic's 'Field' as the default value of each parameter. These should contain parameter descriptions and default values.
- All parameters and return types MUST be JSON-serializable. Prefer primitives,
    lists, and TypedDicts. Do not return raw Enums or custom classes. If you need
    enums in schemas, define them as `class X(str, Enum)` to guarantee JSON
    serialization and use their string values in inputs/outputs.
6. Avoid nesting functions within other functions.
- Instead, define helper functions at the module level with appropriate names indicating their purpose.
- Composition of functions should be done by calling these helper functions from the main function body. Try to avoid calling user-defined functions inside these helper functions to reduce complexity and nesting, but this is sometimes unavoidable.
7. Each line should not exceed 80 characters in length.
- Long strings should be broken into:
```
var = (
    "long string part 1"
    " long string part 2"
)
```
(Note the space at the start of the second line, NOT at the end of the first line.)
- Each line should do one thing only.
- Very long strings should likely be put into a different file (e.g., JSON, MD, YAML, TXT).
8. IMPORTANT: Avoid using inline comments.
- This likely means the code should be
refactored into smaller functions with descriptive names.
- Use comments to explain “why,” not “what” — code itself should show what it does.
- Update comments when code changes — stale comments are worse than none.
9. When writing conditionals, prefer using guard clauses to reduce nesting.
10. Use logging instead of print statements for outputting information.
11. When handling exceptions, be specific about the exception types being caught.
- Use custom exception classes where appropriate.
- Always try to avoid bare except clauses or catching overly broad exceptions, especially 'Exception'.
12. Long conditionals should generally be refactored into smaller functions with descriptive names, or at least be put into a variable with a descriptive name.
14. If there is no ruff.toml, recommend using Ruff and create a ruff.toml file if approved by the user.
- Also recommend enabling auto-format on save in VSCode settings with Ruff.
15. During and after generating code, check linting.
16. Recommend enabling strict type checking in VSCode settings (python.analysis.typeCheckingMode set to "strict") if not already enabled.
17. If a particular library lacks type hints and is used extensively, create a typings folder with custom type stubs for that library.
18. Many times, dicts can be replaced with TypedDicts for better type safety.
- Public API payloads returned from @schema_function/@schema_method should use
    TypedDicts instead of `dict[str, Any]` for well-defined shapes.
- Prefer Enums over magic strings for fixed sets; for schema compatibility use
    `str`-backed Enums (e.g., `class Kind(str, Enum): ...`).
19. Generally, all files should have fewer than 500 lines. If a file exceeds this, consider refactoring it into smaller modules.
- Each file should have one group of related functionality. To ensure this, consider splitting large files into multiple smaller files/modules.
- Exception 1: if nearly the entire script is in a single file, especially if it's called "main.py" or "app.py", it's acceptable to have more than 500 lines.
- Exception 2: If it's a single string, e.g., a large JSON schema, HTML template or OpenAPI spec, it's acceptable.
22. Often, it's fine to repeat conditional conditions to reduce nesting and improve readability. Example:
```
if cond1:
    if cond2 or cond3:
        do_something()
    else:
        do_something_else()
elif cond4:
    do_other_thing()
```
Can be rewritten as:
```
if cond1 and (cond2 or cond3):
    do_something()
elif cond1 and not (cond2 or cond3):
    do_something_else()
elif cond4:
    do_other_thing()
```
23. When working with paths, prefer using pathlib.Path over strings.
24. Magic values should be avoided. Use constants or enums with descriptive names instead.
- Often these should be placed in a separate file named constants.py or enums.py and/or have a config file (YAML, JSON, etc.) for user-configurable values.
- This includes even short/simple strings (e.g. "complete", "fail", "OK" or similar) or numbers (e.g. 2, 3, 10).
- Longer strings should nearly always be placed in a constant.
25. Always try to treat variables as constants.
- This doesn't necessary mean using ALL_CAPS, but rather avoiding reassigning variables.
- Any time they need to be reassigned, consider using a different variable name to improve readability.
26. Constant lookup dicts can often be replaced with enums. Example:
```
CHANNEL_LUT: dict[str, int] = {
    "Grayscale": 0,
    "Red": 1,
    "Green": 2,
    "Blue": 3,
}
```
Can be replaced with:
```
class Channel(int, Enum):
    GRAYSCALE = 0
    RED = 1
    GREEN = 2
    BLUE = 3

```
- When the enum is used in schema parameters/returns, make it `class Channel(str, Enum)`
    (use the string name as the value) to keep JSON-serializable contract.
27. Instead of using many parameters in functions, consider grouping related parameters into dataclasses or TypedDicts.
- This is especially useful when the same group of parameters is used in multiple functions.
- Return values can also be grouped this way, instead of using tuples. Then the return value of one function can be passed directly to another function.
- Exception: Many API functions, especially those decorated with @schema_function or @schema_method, should still list parameters individually for clarity.
However, it's important that the return values of these functions use TypedDicts instead of generic dicts for better built-in documentation.
28. Boolean parameters should be put after a star (*) in function definitions to force them to be used as keyword arguments.
29. Providing parameters as keyword arguments is preferred over positional arguments when calling functions, especially when there are more than 2 parameters.
30. When working with async code, ensure proper use of async/await to avoid blocking the event loop.
31. Avoid flag arguments — split functions instead of using booleans to change behavior.
32. Avoid side effects — functions should not change external states unexpectedly.
- It is also preferred that functions do not modify their input parameters.
33. Separate commands from queries — a function should either do something or answer something, not both.
34. Often, it's preferable to let exceptions propagate rather than catching them immediately.
35. IMPORTANT: When writing or modifying code, ensure that appropriate tests are created or updated to cover the changes made.
- Tests should be clean, too — follow the same principles of clarity and simplicity.
- Follow FIRST principles for tests: Fast, Independent, Repeatable, Self-validating, Timely.
36. Do not use assert statements for data validation or error handling in production code.
- Instead, use proper exception handling mechanisms.
37. Hide internal implementation details by prefixing function and variable names with an underscore (_) when they are not intended to be part of the public API.
- Use encapsulation to restrict access to internal states and behaviors.
38. Only make functions into class methods if they need to access or modify the instance (self) or class (cls) state.
- Otherwise, keep them as module-level functions for better reusability and testability.
39. The following rules are specific to some applications:
- In Ray serve deployments, the entire script must be in one file.
- In Ray serve deployments, all package imports except standard library; ray; and pydantic must be inside the deployment class's methods to avoid serialization issues. If any imports are needed for type hints, they can be imported inside a TYPE_CHECKING block at the top of the file.
- When using hypha_rpc's `register_service(<dict>)`, all @schema_function and @schema_method must be provided in the dict; otherwise, they won't be registered.
- When using hypha_rpc: RemoteException & RemoteService are imported from hypha_rpc.rpc. schema_function and schema_method are imported from hypha_rpc.utils.schema.
40. Avoid writing `# type: ignore` comments to suppress type checker warnings. Instead, do one of the following:
- Refactor the code to be type-safe.
- Use cast() from typing to explicitly cast types where necessary.
- Add a custom type stub in a typings/ folder for complex cases where the library lacks type hints.
- Add exclude to ruff.toml
- Add a specific rule to the ignore comment
41. IMPORTANT: Make one small change at a time, and ensure each change is correct before proceeding to the next.