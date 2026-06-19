# sparrow-chat

The official floating chat dock for [sparrow](../README.md) agents. Zero
dependencies, self-injecting CSS, framework-free.

Drop it on any page that talks to a sparrow `Harness` over SSE and you get a
consistent chat UI: a floating action button, a slide-out dock, a conversation
drawer, streaming replies, tool-step chips, and citations.

## Use

```html
<!-- optional: marked for markdown rendering -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="/path/to/sparrow-chat.js"></script>
<script>
  SparrowChat.mount({
    endpoint: '/api/agent/chat',                  // POST {message, conversation_id} -> SSE
    conversationsApi: '/api/agent/conversations', // GET list / GET :id / DELETE :id
    title: 'AI Assistant',
    hint: 'Try: "track RAG progress for me"',
    accent: '#7c3aed',                            // theme color
  });
</script>
```

## Options

| key | default | meaning |
|---|---|---|
| `endpoint` | `/api/agent/chat` | POST `{message, conversation_id}`, responds with SSE events |
| `conversationsApi` | `/api/agent/conversations` | `GET` list, `GET /:id` messages, `DELETE /:id` |
| `title` | `AI Assistant` | dock header title |
| `hint` | `''` | one-line hint shown above the messages |
| `accent` | `#7c3aed` | theme color (button, user bubble, focus) |
| `placeholder` | `Type a message…` | input placeholder |
| `storageKey` | `sparrow_conv_id` | localStorage key for the active conversation id |
| `fabIcon` | `💬` | floating-button glyph |

## Expected server contract

**SSE events** from `endpoint` (one JSON object per `data:` line):
`title` · `tool_call` · `tool_result` · `final` (with `citations`) · `error` —
exactly what `sparrow.Harness.run()` yields.

**Conversations API** (optional; the drawer degrades gracefully if absent):
- `GET conversationsApi` → `[{id, title, msg_count, updated_at}]`
- `GET conversationsApi/:id` → `{messages: [{role, content, tool_steps?, citations?}]}`
- `DELETE conversationsApi/:id`

Markdown is rendered if a global `marked` is present, otherwise plain text.
