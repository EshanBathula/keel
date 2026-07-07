import { Component } from 'react'

// React error boundaries must be class components — there is no hook
// equivalent (as of React 18) for catching render/lifecycle errors in
// descendants. Catches anything an inline try/catch can't: a bug in a
// child's render path, not just a rejected fetch.
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Unhandled error in page:', error, info?.componentStack)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      return (
        <div className="card" style={{ margin: 20 }}>
          <h2>Something went wrong loading this page</h2>
          <p className="muted">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={this.reset}>Try again</button>{' '}
            <button className="btn ghost" onClick={() => window.location.reload()}>Reload page</button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
