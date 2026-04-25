import { useState } from "react";
import axios from "axios";
import { ethers } from "ethers";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function App() {
  const [role, setRole] = useState(null);

  const [account, setAccount] = useState("");
  const [userAddress, setUserAddress] = useState("");

  const [permissionId, setPermissionId] = useState("");

  const [email, setEmail] = useState("");
  const [newPermission, setNewPermission] = useState("");

  const [file, setFile] = useState(null);
  const [myFiles, setMyFiles] = useState([]);
  const [sharedFiles, setSharedFiles] = useState([]);

  const [uploading, setUploading] = useState(false);

  function logout() {
    setRole(null);
    setAccount("");
    setUserAddress("");
    setPermissionId("");
    setEmail("");
    setNewPermission("");
    setFile(null);
    setMyFiles([]);
    setSharedFiles([]);
  }

  // OWNER LOGIN
  async function connectWallet() {
    const provider = new ethers.BrowserProvider(window.ethereum);
    const accounts = await provider.send("eth_requestAccounts", []);

    const addr = accounts[0];

    setAccount(addr);
    setRole("owner");

    await loadFiles(addr);
  }

  // USER LOGIN
  async function loginUser() {
    const formData = new FormData();
    formData.append("permission_id", permissionId);

    const res = await axios.post(`${BACKEND_URL}/login`, formData);

    if (res.data.error) {
      alert(res.data.error);
      return;
    }

    const addr = res.data.user_address;

    setUserAddress(addr);
    setRole("user");

    await loadFiles(addr);
  }

  // CREATE PERMISSION
  async function createPermission() {
    const formData = new FormData();
    formData.append("email", email);

    const res = await axios.post(`${BACKEND_URL}/create-permission`, formData);

    if (res.data.status === "exists") {
      alert("Permission already exists");
    }

    setNewPermission(res.data.permission_id);
  }

  // LOAD FILES
  async function loadFiles(addr) {
    const my = await axios.get(`${BACKEND_URL}/my-files/${addr}`);
    const shared = await axios.get(`${BACKEND_URL}/shared-files/${addr}`);

    setMyFiles(my.data || []);
    setSharedFiles(shared.data || []);
  }

  // UPLOAD
  async function uploadFile() {
    if (!file) {
      alert("Please select a file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    if (role === "owner") {
      formData.append("user_address", account);
    } else {
      formData.append("permission_id", permissionId);
    }

    setUploading(true);
    await axios.post(`${BACKEND_URL}/upload`, formData);
    setUploading(false);

    await loadFiles(role === "owner" ? account : userAddress);
  }

  async function refresh() {
    const addr = role === "owner" ? account : userAddress;
    await loadFiles(addr);
  }

  // =========================
  // UI GIỮ NGUYÊN 100%
  // =========================

  if (!role) {
    return (
      <div className="login-container">
        <h1>Web3 File Storage</h1>

        <div className="card">
          <h3>Owner Login</h3>
          <button onClick={connectWallet}>Connect Wallet</button>
        </div>

        <div className="card">
          <h3>User Login</h3>

          <input
            placeholder="Permission ID"
            value={permissionId}
            onChange={(e) => setPermissionId(e.target.value)}
          />

          <button onClick={loginUser}>Login</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="header">
        <h1>
          {role === "owner" ? "Owner Dashboard" : "User Dashboard"}
        </h1>

        <div className="header-right">
          <button onClick={logout}>Logout</button>

          <span className="wallet">
            {(role === "owner" ? account : userAddress)?.slice(0, 6)}...
          </span>
        </div>
      </div>

      {role === "owner" && (
        <div className="card">
          <h2>Create Permission</h2>

          <input
            placeholder="User Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <button onClick={createPermission}>
            Generate Permission ID
          </button>

          {newPermission && (
            <p style={{ marginTop: 10 }}>
              Permission ID: <b>{newPermission}</b>
            </p>
          )}
        </div>
      )}

      <div className="card">
        <h2>Upload File</h2>

        <input type="file" onChange={(e) => setFile(e.target.files[0])} />

        <div className="actions">
          <button onClick={uploadFile} disabled={uploading}>
            {uploading ? "Uploading..." : "Upload"}
          </button>

          <button className="secondary" onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card">
        <h2>My Files</h2>

        {myFiles.length === 0 ? (
          <p className="empty">No files uploaded</p>
        ) : (
          <div className="grid">
            {myFiles.map((f) => (
              <div key={f.id} className="file-card">
                <h4>{f.filename}</h4>
                <p>
                  {new Date(f.timestamp * 1000).toLocaleString("en-GB")}
                </p>
                <a href={f.ipfs_url} target="_blank" rel="noreferrer">
                  Open
                </a>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Shared Files</h2>

        {sharedFiles.length === 0 ? (
          <p className="empty">No shared files</p>
        ) : (
          <div className="grid">
            {sharedFiles.map((f) => (
              <div key={f.id} className="file-card">
                <h4>{f.filename}</h4>
                <p>
                  {new Date(f.timestamp * 1000).toLocaleString("en-GB")}
                </p>
                <a href={f.ipfs_url} target="_blank" rel="noreferrer">
                  Open
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;