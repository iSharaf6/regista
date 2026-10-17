# Submission checklist (the only things left that need you)

Deadlines are in Pacific Time (the rules' time zone), with Sydney/Melbourne time (AEDT) in brackets. Tick these off in order.

- [ ] **Register by Tue Oct 20, 12:00 PT** (Wed Oct 21, 6:00 am AEDT). Go to https://aka.ms/insidethegame, click
      *Register* and create the project page.
- [x] **Azure deploy:** live at https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io (Foundry gpt-4.1-mini).
      To redeploy: `azd provision`, then `infra/deploy-image.sh`.
- [x] **Public GitHub repo:** https://github.com/iSharaf6/regista
- [ ] **Record the video (strictly under 2 minutes)** by following `docs/demo-script.md` shot by shot. Use no
      copyrighted music. Upload it to YouTube as *Unlisted* or *Public*; a public URL is required.
- [ ] **Fill in the project page.** Copy the sections from `docs/submission.md` and paste in three links: the repo URL, the
      video URL, and the live URL (from the deploy session, or `azd env get-value REGISTA_URL`).
- [ ] **Pick the category:** "Best Multi-Agent Orchestration" (the rules also call it "Best Multi-Agent System"). Grand Prizes are judged automatically.
- [ ] **Submit by Tue Oct 27, 23:59 PT** (Wed Oct 28, 5:59 pm AEDT). Aim for the 25th, so there is slack if an upload fails.
- [ ] **Keep the live site reachable until judging ends: Tue Nov 10, 23:59 PT** (Wed Nov 11, 6:59 pm AEDT). Rules §4.8
      require judges to have access to a working project until then. Only after that, run `azd down`.

Winners are announced by Fri Nov 20, 23:59 PT (Sat Nov 21, 6:59 pm AEDT). After the deadline, don't make substantive
changes to the submitted project.
