import { useState } from "react";
import { setCredentials, api } from "@/lib/api";

interface Props {
  onAuthenticated: () => void;
}

export function LoginGate({ onAuthenticated }: Props) {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(false);
    setCredentials(user, pass);
    try {
      await api.getStatus();
      onAuthenticated();
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border bg-card p-6 shadow-sm"
      >
        <h1 className="text-lg font-semibold">Auto-Trader Login</h1>
        {error && (
          <p className="text-sm text-red-500">Invalid credentials</p>
        )}
        <input
          type="text"
          placeholder="Username"
          value={user}
          onChange={(e) => setUser(e.target.value)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          autoFocus
        />
        <input
          type="password"
          placeholder="Password"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
