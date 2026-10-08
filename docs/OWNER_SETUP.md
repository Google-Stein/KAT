# Owner setup and permissions

The owner directs KAT's product. Agents implement, test, document, and publish code. You do not need to write application code.

## What you need to do

### To use KAT on Windows

1. Download the `kat-windows-installer` artifact and run its NSIS setup for your current Windows account. Launch KAT from the installed shortcut. Portable alternative: download the `kat-windows-executable` artifact from a successful **KAT checks** GitHub Actions run, then extract the whole archive. Keep `kat-desktop.exe` beside the included `binaries/` directory. Alternatively, use the Windows developer/build scripts in README.md.
2. Launch KAT, open Settings, and choose **Set API key**. The native Windows credential dialog accepts your OpenAI API key and saves it in your own Windows Credential Manager. This requires an OpenAI API account/key with access to the chosen model. The provider key does not enter the React interface or Git repository.
3. Review application-launch approval cards when you ask KAT to open a registered application. You can allow or deny each request.

The Windows key-entry feature is separate from a cloud environment secret. A key saved on your Windows machine is not automatically shared with cloud tasks. Installing Microsoft developer prerequisites is needed only for local source builds; a successful CI artifact contains the packaged Core runtime.

### To enable live model tests in the cloud environment

1. Enter the API key securely in environment settings under the `KAT_OPENAI_API_KEY` requirement. Do not paste it into chat or commit it to `.env`.
2. Review/save the configuration draft. It includes installation/startup instructions and HTTPS destinations needed for OpenAI and GitHub API access.
3. Publish the environment. Code publication to GitHub and cloud environment publication are separate operations.

Saving a draft alone does not inject the key or apply its network policy to the current machine. After configuration is active, agents retry affected operations and report actual results. Offline installation/tests and repository publication do not need your OpenAI key.

## Access and scope

| Access | Purpose | Owner action |
| --- | --- | --- |
| GitHub code and workflow write access | Publish implementation and CI files | Already working; the owner authorized publication |
| HTTPS to `api.github.com` | Inspect Actions/API results using existing authentication | Domain addition saved in cloud draft; review/save settings |
| HTTPS to `api.openai.com` | Send model requests | Domain saved in cloud draft; review/save settings and configure key |
| OpenAI API key | Authenticate model requests | Supply securely in Windows credential dialog or cloud environment settings |
| Windows Credential Manager | Store/read KAT's own `KAT/OpenAI` entry for the current user | Explicit key setup through KAT Settings; no administrator grant |
| Registered application launch | Open an explicitly allowlisted application | Approve each request in KAT |

No unrestricted internet grant, administrator elevation, arbitrary shell tool, autonomous scheduling, browser automation, email, or calendar permission is being requested. GitHub API authorization is checked only after its network destination becomes reachable; a blocked hostname is not evidence that another GitHub token is needed.

## Current delivery limits

Use [VALIDATION.md](VALIDATION.md) for measured results and the latest published commit. A build passing in Linux is distinct from a Windows build and launch. Initial artifacts are unsigned; signed distribution and release/upgrade testing remain separate release-hardening work. Local history is stored in SQLite and is not encrypted by KAT itself.
