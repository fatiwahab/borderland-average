// Thin wrapper around Firebase so main.py only deals with paths and JSON strings.
// Add ?emulator to the page URL to use the local Firebase emulator instead of the real project.
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js";
import { getAuth, signInAnonymously, connectAuthEmulator } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js";
import {
  getDatabase, connectDatabaseEmulator, ref, get, set, update, remove, onValue, onDisconnect,
} from "https://www.gstatic.com/firebasejs/11.10.0/firebase-database.js";
import { firebaseConfig } from "./firebase-config.js";

const useEmulator = new URLSearchParams(location.search).has("emulator");
const config = useEmulator
  ? { apiKey: "demo-key", projectId: "demo-borderland", databaseURL: "http://127.0.0.1:9000?ns=demo-borderland-default-rtdb" }
  : firebaseConfig;

if (!config.databaseURL || config.databaseURL.includes("PASTE")) {
  window.netStatus = "not-configured";
} else {
  const app = initializeApp(config);
  const auth = getAuth(app);
  const db = getDatabase(app);
  if (useEmulator) {
    connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true });
    connectDatabaseEmulator(db, "127.0.0.1", 9000);
  }

  const toJson = (value) => (value === null || value === undefined ? "" : JSON.stringify(value));
  const errorCode = (err) => String((err && (err.code || err.message)) || err);
  const finish = (promise, done, fail) =>
    promise.then((value) => done && done(value)).catch((err) => fail && fail(errorCode(err)));

  window.net = {
    signIn: (done, fail) => finish(signInAnonymously(auth).then((cred) => cred.user.uid), done, fail),
    get: (path, done, fail) => finish(get(ref(db, path)).then((snap) => toJson(snap.val())), done, fail),
    set: (path, json, done, fail) => finish(set(ref(db, path), JSON.parse(json)), done, fail),
    update: (path, json, done, fail) => finish(update(ref(db, path), JSON.parse(json)), done, fail),
    remove: (path, done, fail) => finish(remove(ref(db, path)), done, fail),
    // calls changed(json) now and every time the data at path changes; returns a function that stops listening
    listen: (path, changed, fail) =>
      onValue(ref(db, path), (snap) => changed(toJson(snap.val())), (err) => fail && fail(errorCode(err))),
    // when this browser loses its connection, Firebase applies this update for us
    onDisconnectUpdate: (path, json) => onDisconnect(ref(db, path)).update(JSON.parse(json)),
    cancelOnDisconnect: (path) => onDisconnect(ref(db, path)).cancel(),
    onConnected: (changed) => onValue(ref(db, ".info/connected"), (snap) => changed(snap.val() === true)),
  };
  window.netStatus = "ready";
}
