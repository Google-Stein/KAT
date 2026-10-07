"""Central tool policy. Risk metadata is mandatory and cannot be chosen by a model."""

from dataclasses import dataclass

from kat_core.tools import ToolRisk


@dataclass(frozen=True)
class PermissionPolicy:
    require_approval_for_low_risk: bool = False

    def requires_approval(self, risk: ToolRisk) -> bool:
        return risk != ToolRisk.LOW or self.require_approval_for_low_risk
