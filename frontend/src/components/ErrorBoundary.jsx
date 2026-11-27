import React from 'react';
import ErrorPage from './ErrorPage.jsx';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch() {
    // Never render or expose stack traces, DSNs, or tokens to the UI.
  }

  render() {
    if (this.state.hasError) {
      return <ErrorPage status={500} onRetry={() => location.reload()} />;
    }
    return this.props.children;
  }
}
