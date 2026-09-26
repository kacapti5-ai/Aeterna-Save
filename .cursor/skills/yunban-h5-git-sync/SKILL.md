---
name: yunban-h5-git-sync
description: >-
  After any code change in this project (永恒守护科技 / Aeterna Save), commit and push
  to https://github.com/kacapti5-ai/Aeterna-Save.git on main.
  Use when finishing a task on this site, or when the user mentions GitHub sync
  or uploading changes.
---

# Aeterna Save Git Sync

以后每次修改完都上传到这个地址：https://github.com/kacapti5-ai/Aeterna-Save.git

保证每次操作完这个项目都提交到这个地址。

## Mandatory rule

**Every task** that creates or edits files in this project MUST end with commit + push to:

**https://github.com/kacapti5-ai/Aeterna-Save.git** (branch `main`)

Do this automatically at the end of your turn — do not wait for the user to ask.

Skip only if the user explicitly says **不要提交**, **do not commit**, or **do not push**.

## Quick path

```bash
bash scripts/sync-to-github.sh "feat: short summary of why"
```

Never force-push `main` unless asked. Never commit `.env` or secrets.
