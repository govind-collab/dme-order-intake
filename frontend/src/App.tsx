import { useState } from "react";

import { AuthForm } from "./components/AuthForm";
import { Workspace } from "./components/Workspace";

/** Show the sign-in form until there is a token, then the order review workspace. */
export default function App() {
  // Kept in memory only, so a reload or closed tab signs the reviewer out
  const [token, setToken] = useState<string | null>(null);

  if (token === null) {
    return <AuthForm onSignedIn={setToken} />;
  }
  return <Workspace token={token} onSignOut={() => setToken(null)} />;
}
