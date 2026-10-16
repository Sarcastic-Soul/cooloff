# rolling_risk_gate (Strands Decider 2B decision pattern, label: `policy`)

**What it does.** It watches a stream (a phone call, a chat, a log) one sentence at a time. Decider 2B answers a few typed
questions about each sentence. The gate keeps a moving level per signal and decides: green (do nothing), amber (warn),
red (hold the risky tool and ask a human). Red needs two different kinds of signal, so one odd sentence never locks anyone out.

**Where Decider sits in the agent's path.** `TransactionHold` is a Strands `InterventionHandler`. On `before_tool_call` it
reads the gate and returns `Proceed` or `Confirm`. `Confirm` pauses the agent (`stop_reason == "interrupt"`) until a human
answers. The decision is made by Decider's answers and plain code, not by the agent's own LLM.

## The typed questions (`questions.py`)

| Question | Type | Options |
|---|---|---|
| `payment_ask` | choice | none, known_bill_known_payee, gift_cards_crypto_or_wire, remote_access_request, password_or_code_request |
| `impersonation` | choice | none, relative_in_trouble, bank_or_fraud_dept, government, tech_support, romance, prize |
| `secrecy` | yes/no (`noul`) | does the speaker ask the listener to hide this from family or bank staff |
| `pressure` | score (0 to 2) | none, some urgency, strong threats or demands to act now |

All four go in **one request** to `POST /v1/systemone`, so Decider shares the work across them.

## How answers become a decision

- Each question becomes a number between 0 and 1 (`questions.py`): for a choice, the probability mass on the dangerous options,
  not the single picked option. On our 100 hand-labeled sentences this separated scams from normal talk much better
  (payment ask: 0.995 to 1.0 AUC from probabilities, against 83% recall for the picked option).
- A signal level goes up fast (`attack`, scaled by Decider's confidence) and down slowly (`release`). A shaky answer barely moves it.
- A signal is **active** at or above `active_above`, and inactive again below `inactive_below` (hysteresis).
- Signals sit in groups. **Red needs two active signals from different groups. Amber is one.**
- Red is latched. Only `gate.clear()` (a human decision) returns it to green.
- All numbers live in `thresholds.yaml`.

## Use it in a few lines

```python
from patterns.rolling_risk_gate import make_gate, QUESTIONS
from patterns.rolling_risk_gate.hold import TransactionHold
from strands import Agent

gate = make_gate()                         # reads thresholds.yaml
hold = TransactionHold(gate, {"send_money", "pay_bill"},
                       payee_known=lambda tool_input: tool_input["payee"] in MY_KNOWN_PAYEES,
                       on_hold=lambda tool, args, state: notify_family(tool, args))
agent = Agent(tools=[send_money, pay_bill], interventions=[hold])

for sentence in stream:                    # outside the agent's model call
    answers = decider_answers(sentence, QUESTIONS)   # POST /v1/systemone, see agent/decider_client.py
    state = gate.update(answers)           # green, amber or red
```

When the gate is red and the agent tries `send_money`, the agent stops with `stop_reason == "interrupt"`. Ask the human, then
resume with `agent([{"interruptResponse": {"interruptId": id, "response": "yes"}}])`. Any other response cancels the tool call.

## Reuse it for something else

Only `questions.py` is specific to scam calls. Swap the questions and the `Signal` list and the same gate works for other streams.
`examples/kids_chat/` does this for a child's chat (secrecy, "move to another app", requests for photos or addresses) with
no money involved. A support-call or content-review stream would work the same way.

## Limits

- Decider reads one sentence at a time here. The gate supplies the memory.
- Impersonation is the weakest signal (about 74% exact on our set). The gate treats it as supporting evidence, not as proof.
- 4,096 tokens is the Decider input limit, so keep each state short (one sentence is plenty).
