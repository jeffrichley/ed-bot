# Classification

`ThreadClassifier` assigns two orthogonal labels to every thread: a `ThreadStatus` reflecting the current state of the discussion, and a `QuestionType` reflecting the nature of the question. Together they drive priority scoring and prompt selection.

## ThreadStatus

Defined in `ed_bot.engine.classifier`:

```python
class ThreadStatus(str, Enum):
    UNANSWERED    = "unanswered"
    STUDENT_ONLY  = "student_only"
    NEEDS_FOLLOWUP = "needs_followup"
    ENDORSED      = "endorsed"
    STAFF_ANSWERED = "staff_answered"
    RESOLVED      = "resolved"
    PRIVATE_FLAGGED = "private_flagged"
```

| Status | Meaning |
|--------|---------|
| `unanswered` | No comments of any kind |
| `student_only` | Has comments but none from staff |
| `needs_followup` | Staff has responded but a follow-up is needed |
| `endorsed` | An answer has been endorsed by staff |
| `staff_answered` | Staff has responded without endorsement |
| `resolved` | Marked answered by the poster |
| `private_flagged` | Private thread requiring immediate review |

### Attention statuses

The following statuses are considered to require attention:

```python
ATTENTION_STATUSES = {
    ThreadStatus.UNANSWERED,
    ThreadStatus.STUDENT_ONLY,
    ThreadStatus.NEEDS_FOLLOWUP,
    ThreadStatus.PRIVATE_FLAGGED,
}
```

Use `ThreadClassifier.needs_attention(status)` to check.

## QuestionType

```python
class QuestionType(str, Enum):
    LOGISTICS       = "logistics"
    SETUP           = "setup"
    CONCEPTUAL      = "conceptual"
    PROJECT_HELP    = "project_help"
    TEACHING_MOMENT = "teaching_moment"
    INTEGRITY_RISK  = "integrity_risk"
```

| Type | Description |
|------|-------------|
| `logistics` | Due dates, submission instructions, office hours, policies |
| `setup` | Environment issues, package installation, path problems |
| `conceptual` | Understanding algorithms, math, or theoretical concepts |
| `project_help` | Debugging, approach guidance for a graded assignment |
| `teaching_moment` | Deep question that warrants a thorough educational response |
| `integrity_risk` | Appears to be asking for solution code or violating academic honesty |

## Priority scoring

`ThreadClassifier.priority_score(status)` returns an integer indicating urgency. Higher values mean more urgent:

| Status | Score |
|--------|------:|
| `private_flagged` | 100 |
| `unanswered` | 90 |
| `student_only` | 70 |
| `needs_followup` | 50 |
| `endorsed` | 0 |
| `staff_answered` | 0 |
| `resolved` | 0 |

The draft queue maps these scores to three priority levels via `compute_priority()`:

```python
# ed_bot.queue.priority
def compute_priority(status: ThreadStatus) -> str:
    if status in (ThreadStatus.UNANSWERED,
                  ThreadStatus.STUDENT_ONLY,
                  ThreadStatus.PRIVATE_FLAGGED):
        return "high"
    if status == ThreadStatus.NEEDS_FOLLOWUP:
        return "medium"
    return "low"
```

The `DraftQueue.list()` method sorts drafts by priority (`high → medium → low`) so reviewers always see the most urgent items first.

## Classifying a thread

```python
from ed_bot.engine.classifier import ThreadClassifier

status = ThreadClassifier.classify_status(
    comment_count=0,
    has_staff_response=False,
    is_endorsed=False,
    is_answered=False,
)
# ThreadStatus.UNANSWERED

print(ThreadClassifier.needs_attention(status))  # True
print(ThreadClassifier.priority_score(status))   # 90
```

## Future: LLM-based QuestionType classification

The current `ed answer` command defaults to `QuestionType.PROJECT_HELP`. Full LLM-based classification is planned — it will use a lightweight Claude call with a structured output schema to determine the question type before generating the draft.
