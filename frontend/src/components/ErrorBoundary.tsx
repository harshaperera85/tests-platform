// App-level error boundary: catches render errors and shows a recoverable fallback
// instead of a white screen.
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Alert, Button } from "./ui";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-2xl px-6 py-16">
          <Alert tone="error" title="Something went wrong">
            <p>{this.state.error.message}</p>
            <div className="mt-3">
              <Button onClick={() => this.setState({ error: null })}>Try again</Button>
            </div>
          </Alert>
        </div>
      );
    }
    return this.props.children;
  }
}
