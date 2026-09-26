"""Temporary verification matrix (deleted after use). Not a test file."""

import logging
import sys

sys.path.insert(0, "src")
logging.disable(logging.CRITICAL)

from application.chat.task_router import TaskRouter  # noqa: E402
from application.tasks.dealer_details.workflow import DealerDetailsWorkflow  # noqa: E402
from application.tasks.item_lookup.workflow import ItemLookupWorkflow  # noqa: E402
from application.tasks.schedule_call.workflow import ScheduleCallWorkflow  # noqa: E402
from domain.enums.task_type import TaskType  # noqa: E402
from domain.enums.workflow_state import (  # noqa: E402
    LEGAL_TRANSITIONS,
    WorkflowState,
    ensure_legal_transition,
)
from domain.exceptions import InvalidTransitionError  # noqa: E402
from models.inputs.task import TaskDecision  # noqa: E402
from models.outputs.car import CarSearchResult  # noqa: E402

ok = True


def route(t: TaskType, s: WorkflowState) -> TaskType:
    return TaskRouter.route(TaskDecision(task_type=t.value, confidence=0.9, reason="x"), s)


pinned = [
    ("ITEM@START", route(TaskType.ITEM_LOOKUP, WorkflowState.START), TaskType.ITEM_LOOKUP),
    (
        "ITEM@AWAITING_CAR",
        route(TaskType.ITEM_LOOKUP, WorkflowState.AWAITING_CAR),
        TaskType.ITEM_LOOKUP,
    ),
    (
        "DETAILS@AWAITING_ACTION",
        route(TaskType.DEALER_DETAILS, WorkflowState.AWAITING_ACTION),
        TaskType.DEALER_DETAILS,
    ),
    (
        "SCHEDULE@AWAITING_ACTION",
        route(TaskType.SCHEDULE_CALL, WorkflowState.AWAITING_ACTION),
        TaskType.SCHEDULE_CALL,
    ),
    ("DETAILS@START", route(TaskType.DEALER_DETAILS, WorkflowState.START), TaskType.UNKNOWN),
    ("SCHEDULE@START", route(TaskType.SCHEDULE_CALL, WorkflowState.START), TaskType.UNKNOWN),
    ("ITEM@COMPLETE", route(TaskType.ITEM_LOOKUP, WorkflowState.COMPLETE), TaskType.UNKNOWN),
    ("UNKNOWN", route(TaskType.UNKNOWN, WorkflowState.START), TaskType.UNKNOWN),
]
for name, got, want in pinned:
    good = got == want
    ok &= good
    print(("OK  " if good else "FAIL"), name, "->", got.value)

found = CarSearchResult(status="found", cars=[], candidates=[])
multi = CarSearchResult(status="multiple", cars=[], candidates=[])
missing = CarSearchResult(status="not_found", cars=[], candidates=[])

targets = {
    TaskType.ITEM_LOOKUP: [
        ItemLookupWorkflow.advance(found, True),
        ItemLookupWorkflow.advance(found, False),
        ItemLookupWorkflow.advance(multi),
        ItemLookupWorkflow.advance(missing),
    ],
    TaskType.DEALER_DETAILS: [
        DealerDetailsWorkflow.advance(True),
        DealerDetailsWorkflow.advance(False),
    ],
    TaskType.SCHEDULE_CALL: [
        ScheduleCallWorkflow.advance(True),
        ScheduleCallWorkflow.advance(False),
    ],
}
error_targets = {
    TaskType.ITEM_LOOKUP: [WorkflowState.AWAITING_CAR],
    TaskType.DEALER_DETAILS: [WorkflowState.AWAITING_ACTION],
    TaskType.SCHEDULE_CALL: [WorkflowState.AWAITING_ACTION, WorkflowState.AWAITING_DATETIME],
}

illegal = []
for task, entries in TaskRouter.TASK_ENTRY_STATES.items():
    for e in entries:
        for t in targets[task] + error_targets[task]:
            try:
                ensure_legal_transition(e, t, selected_car_id="C-1", selected_dealer_id="D-1")
            except InvalidTransitionError:
                illegal.append(f"{task.value}: {e.value} -> {t.value}")
print("router x workflow matrix illegal:", illegal or "none")
ok &= not illegal

missing_loops = [s.value for s in WorkflowState if s not in LEGAL_TRANSITIONS.get(s, frozenset())]
print("states missing self-loop:", missing_loops or "none")
ok &= not missing_loops

for cur, tgt in [
    (WorkflowState.START, WorkflowState.COMPLETE),
    (WorkflowState.AWAITING_CAR, WorkflowState.DEALER_DETAILS_SHOWN),
]:
    try:
        ensure_legal_transition(cur, tgt)
        print("FAIL should raise:", cur.value, tgt.value)
        ok = False
    except InvalidTransitionError:
        print("OK   raises:", cur.value, "->", tgt.value)

try:
    ensure_legal_transition(WorkflowState.AWAITING_ACTION, WorkflowState.COMPLETE)
    print("FAIL: COMPLETE gate did not fire")
    ok = False
except InvalidTransitionError:
    print("OK   COMPLETE gate fires without selections")

try:
    ensure_legal_transition(
        WorkflowState.AWAITING_ACTION,
        WorkflowState.COMPLETE,
        selected_car_id="C",
        selected_dealer_id="D",
    )
    print("OK   COMPLETE allowed with selections")
except InvalidTransitionError:
    print("FAIL: COMPLETE blocked despite selections")
    ok = False

print("RESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
