# Writing Tests

## What Tests Should Focus On:
1. **Real user workflows** - not implementation details
2. **Failure modes** - how does it break and recover?
3. **Configuration variations** - different setups users actually use
4. **Integration points** - where components interact
5. **Performance characteristics** - memory, startup time, responsiveness

## What Tests Should Avoid:
1. Testing framework code (Textual, FastMCP internals)
2. Testing language features (Python dict access, etc.)
3. Testing third-party library behavior
4. Overly specific string matching
5. Implementation details that could change