# Roadmap

## Milestone 1: Windows release hardening

Exercise installation, packaged desktop startup/shutdown, WebView2 prerequisites, upgrade behavior, and crash recovery on Windows. Add signed release artifacts, native end-to-end tests, dependency update automation, and a repeatable release checklist. Add secure API-key entry backed by Windows Credential Manager without moving keys into the webview or database.

## Milestone 2: Better conversation lifecycle

Add streaming replies with cancellation, context-window budgeting, session rename/export/delete with explicit confirmation, and tests for interrupted turns. Retain a readable transcript and distinguish model failure, cancellation, and successful output. Define data retention and backup/restore behavior.

## Milestone 3: Provider and tool extension contracts

Implement a second runtime adapter behind the existing protocol. Add explicit user-managed application registrations with trusted executable resolution, richer permission policy, scoped grants, approval expiry, and stronger crash/outcome recovery. Test adapter conformance and tool metadata/policy contracts before adding new capabilities.

## Later, only after product approval

Consider semantic memory, planning, voice, scheduled actions, connected services, computer interaction, and controlled autonomy as separate product/security projects. They are not silently enabled by this foundation. Each must specify consent, scope, persistence, observability, cancellation, and failure behavior before implementation.
