from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ToolCallPolicy:
    allowed_tool_names: frozenset[str]
    max_total_calls: int = 4
    max_calls_per_tool: int = 1
    fail_on_policy_violation: bool = True
    
@dataclass(slots=True)
class ToolCallBudgetState:
    total_calls: int = 0
    per_tool_calls: dict[str, int] = field(default_factory=dict)

    def can_call(self, tool_name: str, policy: ToolCallPolicy) -> bool:
        if tool_name not in policy.allowed_tool_names:
            return False
        
        if self.total_calls >= policy.max_total_calls:
            return False
        
        tool_count = self.per_tool_calls.get(tool_name, 0)
        
        return not tool_count >= policy.max_calls_per_tool

    def mark_called(self, tool_name: str) -> None:
        self.total_calls += 1
        self.per_tool_calls[tool_name] = self.per_tool_calls.get(tool_name, 0) + 1