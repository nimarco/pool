# IAM policy documents for the AgentCore runtime

`agentcore.json` lists these under the runtime's `additionalPolicies`. The AgentCore CDK
construct resolves each path **relative to `codeLocation`** (this directory's parent) and
attaches the document to the runtime's execution role as an inline policy. Nothing here
is a credential; these are grants, and they are in version control precisely so that what
the deployed agent may touch is reviewable in a diff.

## `agentcore-dynamodb.json`

The runtime coordinates inside the same DynamoDB workspace the browser is looking at, so
it needs to read and write that table. Three actions, one table, and every omission is
deliberate:

| Action | Granted | Why |
| --- | --- | --- |
| `GetItem`, `Query` | yes | Every repository read. |
| `PutItem` | yes | Every repository write — pools, memberships, decisions, activity, the run record. |
| `DeleteItem`, `BatchWriteItem` | **no** | The only caller is `Repository.reset()`, which empties a whole partition. The runtime never resets a workspace (`agentcore_app.py` refuses to seed a shared store), so the grant would exist solely to let a bug destroy a visitor's session. |
| `UpdateItem` | **no** | The repository writes whole items. Quota and lease counters are the API Lambda's job. |
| `Scan` | **no** | Nothing scans, and a `Scan` is the one call that ignores partition isolation. |
| `*` on any other table | **no** | The resource is one table name. |

The ARN wildcards the account and region rather than naming them. The table name is the
part that identifies the resource; the account is fixed by which account the role lives
in, and hardcoding it into a file in a public repository buys nothing. `infra/` names the
same table explicitly, which is what keeps the two halves of this contract in agreement —
`infra/test_demo_stack.py` asserts it.
