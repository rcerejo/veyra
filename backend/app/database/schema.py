from __future__ import annotations

from collections import deque

from app.database.adapter import TableInfo


class SchemaCatalog:
    def __init__(self, tables: tuple[TableInfo, ...]) -> None:
        self.tables = {table.name: table for table in tables}

    def as_dict(self) -> dict:
        return {
            "tables": [
                {
                    "name": table.name,
                    "columns": [column.__dict__ for column in table.columns],
                    "foreign_keys": [key.__dict__ for key in table.foreign_keys],
                }
                for table in self.tables.values()
            ]
        }

    def prompt_context(self, names: list[str] | None = None) -> str:
        selected = names or list(self.tables)
        lines: list[str] = []
        for name in selected:
            table = self.tables.get(name)
            if not table:
                continue
            columns = ", ".join(f"{c.name} {c.data_type}{' PRIMARY KEY' if c.primary_key else ''}" for c in table.columns)
            lines.append(f"{table.name}({columns})")
            lines.extend(f"FK {table.name}.{fk.column} -> {fk.target_table}.{fk.target_column}" for fk in table.foreign_keys)
        return "\n".join(lines)

    def join_path(self, start: str, target: str) -> list[str] | None:
        if start not in self.tables or target not in self.tables:
            return None
        graph: dict[str, set[str]] = {name: set() for name in self.tables}
        for table in self.tables.values():
            for key in table.foreign_keys:
                graph[table.name].add(key.target_table)
                graph.setdefault(key.target_table, set()).add(table.name)
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            node, path = queue.popleft()
            if node == target:
                return path
            for neighbour in graph[node] - visited:
                visited.add(neighbour)
                queue.append((neighbour, path + [neighbour]))
        return None

