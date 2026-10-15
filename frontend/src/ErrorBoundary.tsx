import {Component, type ReactNode} from 'react';

export default class ErrorBoundary extends Component<{children: ReactNode}, {error: Error | null}> {
  state: {error: Error | null} = {error: null};
  static getDerivedStateFromError(error: Error) {
    return {error};
  }
  render() {
    if (this.state.error)
      return (
        <main className="startup-error" role="alert">
          <h1>Не удалось отобразить AI Workflow Studio</h1>
          <p>
            Возникла ошибка интерфейса. Перезагрузка откроет последнюю сохранённую версию проекта;
            несохранённые изменения будут потеряны.
          </p>
          <pre>{this.state.error.message}</pre>
          <button onClick={() => window.location.reload()}>Перезагрузить приложение</button>
        </main>
      );
    return this.props.children;
  }
}
