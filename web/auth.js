import { PublicClientApplication } from "@azure/msal-browser";

async function initializeHelpdeskAuth() {
  const panel = document.getElementById("authPanel");
  const status = document.getElementById("authStatus");
  const button = document.getElementById("authButton");
  const setStatus = (message) => { if (status) status.textContent = message; };
  const configResponse = await fetch("/api/v1/auth/config", { cache: "no-store" });
  const config = await configResponse.json();
  if (!config.configured) {
    setStatus("Microsoft Entra is not configured. Complete local .env and Entra setup.");
    if (button) button.disabled = true;
    throw new Error("Entra configuration is incomplete.");
  }

  const redirectUri = window.location.origin + window.location.pathname;
  const msalApp = new PublicClientApplication({
    auth: {
      clientId: config.clientId,
      authority: config.authority,
      redirectUri,
      postLogoutRedirectUri: window.location.origin + "/dashboard",
    },
    cache: { cacheLocation: "sessionStorage", storeAuthStateInCookie: false },
  });
  await msalApp.initialize();
  const redirectResult = await msalApp.handleRedirectPromise();
  if (redirectResult?.account) msalApp.setActiveAccount(redirectResult.account);
  let account = msalApp.getActiveAccount() || msalApp.getAllAccounts()[0] || null;
  if (account) msalApp.setActiveAccount(account);

  const render = () => {
    if (account) {
      setStatus(`Signed in: ${account.name || account.username}`);
      if (button) { button.disabled = false; button.textContent = "Sign out"; }
    } else {
      setStatus("Not signed in");
      if (button) { button.disabled = false; button.textContent = "Sign in with Microsoft"; }
    }
  };
  render();

  async function signIn() {
    await msalApp.loginRedirect({ scopes: [config.apiScope], redirectUri });
  }
  async function getToken() {
    if (!account) await signIn();
    try {
      const result = await msalApp.acquireTokenSilent({ account, scopes: [config.apiScope] });
      return result.accessToken;
    } catch (error) {
      if (error && (error.name === "InteractionRequiredAuthError" || error.errorCode === "interaction_required")) {
        await msalApp.acquireTokenRedirect({ account, scopes: [config.apiScope], redirectUri });
        return null;
      }
      throw error;
    }
  }
  async function request(url, options = {}) {
    const token = await getToken();
    if (!token) throw new Error("Redirecting to Microsoft sign-in...");
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  }
  async function signOut() {
    await msalApp.logoutRedirect({ account, postLogoutRedirectUri: window.location.origin + "/dashboard" });
  }
  if (button) button.addEventListener("click", async () => {
    button.disabled = true;
    try { if (account) await signOut(); else await signIn(); }
    catch (error) { setStatus(`Authentication error: ${error.message}`); button.disabled = false; }
  });

  return {
    request,
    isSignedIn: () => Boolean(account),
    account: () => account,
    signIn,
    signOut,
  };
}

window.ITHelpdeskAuthReady = initializeHelpdeskAuth().then((auth) => {
  window.ITHelpdeskAuth = auth;
  window.dispatchEvent(new CustomEvent("it-helpdesk-auth-ready"));
  return auth;
}).catch((error) => {
  const status = document.getElementById("authStatus");
  if (status) status.textContent = error.message;
  console.error("IT Help Desk authentication initialization failed:", error);
  throw error;
});
