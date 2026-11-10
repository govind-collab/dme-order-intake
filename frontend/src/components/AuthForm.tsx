import { useState, type FormEvent } from "react";

import { logIn, messageOf, register } from "../api";

interface AuthFormProps {
  /** Called with the bearer token after a successful sign-up or log-in. */
  onSignedIn: (token: string) => void;
}

/** Let a reviewer log in, or sign up and log in, with email and password. */
export function AuthForm({ onSignedIn }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn(createAccount: boolean) {
    setBusy(true);
    setError(null);
    try {
      if (createAccount) {
        await register(email, password);
      }
      onSignedIn(await logIn(email, password));
    } catch (error) {
      setError(messageOf(error));
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void signIn(false);
  }

  return (
    <main className="auth">
      <h1>DME order intake</h1>
      <p className="muted">Synthetic data only. This demo has no agreements for real patient data.</p>
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password (8 or more characters)
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        <div className="actions">
          <button type="submit" disabled={busy}>
            Log in
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => void signIn(true)}>
            Sign up
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </form>
    </main>
  );
}
