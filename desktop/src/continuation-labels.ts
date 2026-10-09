import type { ContinuationInfo } from './types';

export function continuationExplanation(info: ContinuationInfo): string | null {
  if (info.state !== 'suppressed' && info.state !== 'failed') return null;
  switch (info.reason) {
    case 'cloud_policy':
      return 'File was read locally. Automatic analysis is available only with the original local Ollama request; file contents were not sent to the cloud provider.';
    case 'provider_changed':
      return 'The model or provider configuration changed. The result stays local and the interrupted request was not resumed.';
    case 'conversation_advanced':
      return 'This conversation advanced. The earlier result stays visible locally without resuming the old request.';
    case 'scope_changed':
      return 'The conversation scope changed. The interrupted request was not resumed.';
    case 'approval_denied':
      return 'A request was denied. No further analysis of this task will run automatically.';
    case 'tool_failed':
      return 'A tool failed. The task was not resumed; inspect its result before making a new request.';
    case 'core_restarted':
    case 'request_interrupted':
      return 'KAT stopped before analysis finished. Completed reads remain available locally and will not be repeated automatically.';
    case 'budget_exhausted':
    case 'result_context_limit':
      return 'This task reached its analysis limit. Completed reads remain available; any new request needs its own approvals.';
    default:
      return 'Local analysis could not finish. Completed reads remain available and will not be repeated automatically; no cloud fallback occurred.';
  }
}
