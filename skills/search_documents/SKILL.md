---
name: search_documents
description: Search project files, logs, documentation, and indexed content using full-text, semantic, and structural queries
---

# Search Documents

Perform targeted searches across the codebase, documentation, logs, and any indexed knowledge bases.

## When to Use

- User asks to **find** specific code, text, configuration, or documentation
- Investigating where a function, class, variable, or string literal is used
- Locating files by name, extension, or directory pattern
- Searching indexed collections for semantic matches

## Environment Context

The user has 4 active workspaces (Corpora) mapping to URIs:
- `/Users/yamai/ai/Raphael` -> `/Users/yamai/ai/Raphael`
- `/Users/yamai/ai/agent_ecosystem` -> `/Users/yamai/ai/agent_ecosystem`
- `/Users/yamai/ai/network_observatory` -> `Yamai7354/network_observatory`
- `/Users/yamai/ai/portfolio` -> `/Users/yamai/ai/portfolio`

When searching, prioritize using these directories as SearchPaths for codebase search or corresponding corpus names for semantic search.

## Workflow

### 1. Determine Search Type

| Need                              | Tool                    | When                                     |
| --------------------------------- | ----------------------- | ---------------------------------------- |
| Exact text / pattern in files     | `grep_search`           | Known string, regex pattern, symbol name |
| File by name / extension          | `find_by_name`          | Looking for files matching a glob        |
| Semantic / fuzzy search           | `mcp_airweave_search-*` | Conceptual queries, natural language     |
| Code symbols (functions, classes) | `view_code_item`        | Need the full body of a known symbol     |
| Directory listing                 | `list_dir`              | Browsing structure                       |

### 2. Execute the Search

#### Text Search (`grep_search`)
```
Query: the exact string or regex to find
SearchPath: start from the most specific directory possible
Includes: use glob filters like "*.py" or "*.ts" to narrow scope
MatchPerLine: true for line-level results, false for file-level
CaseInsensitive: true when casing is uncertain
IsRegex: true only when using regex metacharacters
```

**Tips:**
- Start narrow (specific directory + file type filter), widen only if no results
- For symbol lookups, search the symbol name as a literal string first
- Use `IsRegex: true` for patterns like `def\s+my_func` or `import.*module`

#### File Search (`find_by_name`)
```
Pattern: glob pattern like "*.json" or "config*"
SearchDirectory: root of the search
Extensions: ["py", "ts", "md"] — filter by extension
Type: "file" or "directory"
MaxDepth: limit depth to avoid overwhelming results
```

#### Semantic Search (`mcp_airweave_search-*`)
```
query: natural language description of what you're looking for
search_method: "hybrid" (default), "neural", or "keyword"
limit: keep low (5-10) for focused results
score_threshold: 0.7+ for high-confidence matches
```

### 3. Present Results

- **Summarize** the number of matches found
- **Group** results by file or directory when there are many
- **Show** the most relevant matches with file paths and line numbers
- **Offer** to view full file contents or code items for top results

## Examples

### Find all usages of a function
```
grep_search(Query="process_request", SearchPath="/project/src", Includes=["*.py"], MatchPerLine=true)
```

### Find configuration files
```
find_by_name(Pattern="*.config.*", SearchDirectory="/project", Type="file")
```

### Semantic search for authentication logic
```
mcp_airweave_search(query="user authentication and token validation", limit=5, score_threshold=0.7)
```

## Error Handling

- **No results**: Widen the search — remove filters, broaden the directory, try synonyms
- **Too many results**: Add file type filters, narrow the directory, use more specific terms
- **Regex errors**: Fall back to literal string search with `IsRegex: false`
