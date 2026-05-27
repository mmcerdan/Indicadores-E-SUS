import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="alert alert-error my-4">
          <p className="font-bold">Erro ao renderizar</p>
          <p className="text-sm">{this.state.error.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
