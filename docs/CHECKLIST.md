# Submission checklist (the only things left that need you)

All times are Pacific Time. Tick these off in order.

- [ ] **Register by Mon Oct 20, 12:00 PT.** Go to https://aka.ms/insidethegame, click *Register* and create the project page.
- [x] **Azure deploy:** live at https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io (Foundry gpt-4.1-mini).
      To redeploy: `azd provision`, then `infra/deploy-image.sh`.
- [ ] **Make the GitHub repo public.** Ask Claude to "create the public repo and push". It will run
      `gh repo create regista --public --source . --push` after you confirm.
- [ ] **Record the video (under 2 minutes)** by following `docs/demo-script.md` shot by shot. Use no copyrighted music.
      Upload it to YouTube as *Unlisted* or *Public*; a public URL is required.
- [ ] **Fill in the project page.** Copy the sections from `docs/submission.md` and paste in three links: the repo URL, the
      video URL, and the live URL (from the deploy session, or `azd env get-value REGISTA_URL`).
- [ ] **Pick the category:** "Best Multi-Agent Orchestration" (the rules also call it "Best Multi-Agent System"). Grand Prizes are judged automatically.
- [ ] **Submit by Mon Oct 27, 23:59 PT.** Aim for the 25th, so there is slack if an upload fails.

Optional, if time allows:
- [ ] Run `REGISTA_LLM=foundry regista llm-eval` once Foundry is live, so the README can quote real-model numbers.
- [ ] Keep the Azure deployment running until judging ends on Nov 10 (rules §4.8: judges may test it). Then
      run `azd down`.
