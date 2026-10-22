# AI Web Bridge

AI Web Bridge helps people use browser-based AI assistants alongside their
coding assistant. It can pass a focused task and selected project details to an
AI service in Chrome or Microsoft Edge, then make the answer available for the
person or coding assistant to use.

## What it is for

The project aims to reduce how much repeated background a coding assistant
needs to read. Instead of sending a long conversation or an entire project,
you can provide a short description of the task, the relevant recent changes,
and only the file excerpts needed for that task. The browser-based AI can help
with research, planning, explanations, and drafts; you can then review and use
its response in your project.

This can reduce repeated work and may reduce coding-assistant token use. The
amount saved depends on the task and the assistants you use. It is not
guaranteed, and the coding assistant still needs enough information to apply
and check changes.

## How it works

1. Choose a task and the browser-based AI service you want to use.
2. Provide a concise description and select only the project details that are
   relevant.
3. Review what will be shared, then send it to the selected service.
4. Review the answer and use it in your work. Save any response you want to
   keep where you choose.

Gemini, ChatGPT, and Claude are the currently configured services. The models
and features available depend on what each service shows for your account.
Chrome and Microsoft Edge are supported. Your browser account must be signed in
to the service you want to use.

## What is saved

AI Web Bridge keeps a small amount of information on your computer to help
continue work. This can include the project and service association, a link to
the related conversation, and optional run details such as the service, model
label, time, and references to local files. Optional run details do not include
the prompt, project context, or AI response.

It does not save or copy your browser password, login credentials, or browser
cookies. Your browser continues to manage its own signed-in session. Responses
are saved only if you choose an output location or save them yourself.

## What is shared

When you send a task, the text and project details you selected are sent to the
AI service or services you chose. If you choose more than one service, each
selected service receives the same submitted task details. Each service may
handle or retain submitted information according to its own account settings
and privacy terms.

Review the information before sending it. Include only details you want the
chosen service to receive. The project can filter some sensitive-looking file
names, but it cannot guarantee that every secret inside selected text will be
found.

## Continuing work and choosing a model

Each browser-based AI service has its own conversation history. AI Web Bridge
can remember a conversation link for a project, but it does not automatically
read the full history of another service or transfer that service's account
history. To continue work with a different service, provide a short summary of
the task and changes so far.

You can use model choices that are available in the selected service for your
account. Model names and availability can change, and some choices may depend
on the service's plan or settings.

## Other included tool

The project also includes an optional Google Stitch feature for generating UI
designs. It uses the Stitch service under the user's own account and settings.

## Important limits

AI Web Bridge assists with sending and receiving work; review AI-generated
answers before applying them. It does not guarantee a particular reduction in
token use, access to every model, or uninterrupted support when a provider
changes its website or service.
