import type { Message } from './types';

export function ToolResultView({ message }: { message: Message }) {
  try {
    const data: unknown = JSON.parse(message.content);
    if (
      typeof data === 'object' &&
      data !== null &&
      'tool_name' in data &&
      data.tool_name === 'read_text_file' &&
      'result' in data &&
      typeof data.result === 'object' &&
      data.result !== null &&
      'content' in data.result &&
      typeof data.result.content === 'string'
    ) {
      const result = data.result;
      return (
        <section aria-label="Approved file contents" className="file-preview">
          <strong>Approved text read</strong>
          {'relative_path' in result && typeof result.relative_path === 'string' && (
            <p>{result.relative_path}</p>
          )}
          <pre>{result.content as string}</pre>
          {'truncated' in result && result.truncated === true && (
            <p className="field-hint">Preview truncated to 12,000 characters.</p>
          )}
          <details>
            <summary>Read metadata</summary>
            <pre>{message.content}</pre>
          </details>
        </section>
      );
    }
  } catch {
    /* A malformed transcript stays visible as plain text. */
  }
  return <div className="message-content">{message.content}</div>;
}
