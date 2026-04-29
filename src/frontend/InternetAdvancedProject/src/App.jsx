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

  const [selectedUser, setSelectedUser] = useState(null);

  // SIDEBAR
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [users, setUsers] = useState([]);

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
    setUsers([]);
    setSelectedUser(null);
  }

  async function loadUsers() {
    try {
      const res = await axios.get(`${BACKEND_URL}/users`);
      setUsers(res.data || []);
    } catch {
      setUsers([]);
    }
  }

  async function connectWallet() {
    const provider = new ethers.BrowserProvider(window.ethereum);
    const accounts = await provider.send("eth_requestAccounts", []);
    const addr = accounts[0];

    setAccount(addr);
    setRole("owner");

    await loadFiles(addr);
    await loadUsers();
  }

  async function loginUser() {
    const formData = new FormData();
    formData.append("permission_id", permissionId);

    const res = await axios.post(`${BACKEND_URL}/login`, formData);
    if (res.data.error) return alert(res.data.error);

    const addr = res.data.user_address;
    setUserAddress(addr);
    setRole("user");

    await loadFiles(addr);
  }

  async function createPermission() {
    const formData = new FormData();
    formData.append("email", email);

    const res = await axios.post(`${BACKEND_URL}/create-permission`, formData);
    setNewPermission(res.data.permission_id);
  }

  async function loadFiles(addr) {
    const my = await axios.get(`${BACKEND_URL}/my-files/${addr}`);
    const shared = await axios.get(`${BACKEND_URL}/shared-files/${addr}`);

    setMyFiles(my.data || []);
    setSharedFiles(shared.data || []);
  }
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");

async function uploadFile() {
  if (!file) return alert("Please select a file");

  const formData = new FormData();
  formData.append("file", file);

  if (role === "owner") formData.append("user_address", account);
  else formData.append("permission_id", permissionId);

  setUploading(true);
  setUploadError("");
  setUploadSuccess("");

  try {
    const res = await axios.post(`${BACKEND_URL}/upload`, formData);
    setUploadSuccess(res.data.message);
    await loadFiles(role === "owner" ? account : userAddress);
  } catch (err) {
    const msg = err?.response?.data?.error || err.message || "Something went wrong";
    setUploadError(`Upload failed: ${msg}`);
  } finally {
    setUploading(false);
  }
}

  // LOGIN
  if (!role) {
    return (
      <div className="login-container">
        <h1>Web3 File Storage</h1>

        <div className="card">
          <h3>Owner</h3>
          <button className="primary" onClick={connectWallet}>
            Connect Wallet
          </button>
        </div>

        <div className="card">
          <h3>User</h3>
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
    <>
      {/* SIDEBAR */}
      {role === "owner" && (
        <div className={`sidebar ${sidebarOpen ? "" : "collapsed"}`}>
          <div className="sidebar-header">
            {sidebarOpen && <h3>Users</h3>}

            <button
              className="toggle-btn"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? "←" : "→"}
            </button>
          </div>

          {sidebarOpen && (
            <div className="user-list">
              {users.map((u, i) => {
                const addr = u.user_address || u.address;

                return (
                  <div
                    key={i}
                    className={`user-item ${
                      selectedUser === addr ? "active" : ""
                    }`}
                    onClick={() =>
                      setSelectedUser(
                        selectedUser === addr ? null : addr
                      )
                    }
                  >
                    {u.email || addr?.slice(0, 6)}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* MAIN */}
      <div
        className={`app ${
          role === "owner" ? "with-sidebar" : ""
        } ${!sidebarOpen ? "collapsed" : ""}`}
      >
        <div className="header">
          <h1>{role === "owner" ? "Owner" : "User"} Dashboard</h1>

          <div className="header-right">
            <button onClick={logout}>Logout</button>
            <span className="wallet">
              {(role === "owner" ? account : userAddress)?.slice(0, 6)}...
            </span>
          </div>
        </div>

        {/* Upload */}
        <div className="section">
          <div className="card main">
            <h2>Upload</h2>

            <input type="file" onChange={(e) => setFile(e.target.files[0])} />

            <div className="actions">
              <button
                className="primary"
                onClick={uploadFile}
                disabled={uploading}
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>

              <button onClick={refresh}>Refresh</button>
            </div>
            {uploadSuccess && (
                <p style={{ color: "green", marginTop: 8 }}>{uploadSuccess}</p>
            )}
            {uploadError && (
                <p style={{ color: "red", marginTop: 8 }}>{uploadError}</p>
            )}
          </div>
        </div>

        {/* OWNER */}
        {role === "owner" && (
          <div className="section">
            <div className="card">
              <h2>Create Permission</h2>

              <input
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <button className="primary" onClick={createPermission}>
                Generate
              </button>

              {newPermission && (
                <p style={{ marginTop: 10 }}>
                  ID: <b>{newPermission}</b>
                </p>
              )}
            </div>
          </div>
        )}

        {/* FILES */}
        <div className="section row">
          {/* MY FILES */}
          <div className="card">
            <h2>My Files</h2>

            {myFiles.length === 0 ? (
              <p className="empty">Empty</p>
            ) : (
              <div className="grid">
                {myFiles.map((f) => (
                  <div key={f.id} className="file-card">
                    <div>
                      <h4>{f.filename}</h4>
                      <p>
                        {new Date(f.timestamp * 1000).toLocaleString()}
                      </p>
                    </div>

                    <a href={f.ipfs_url} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* SHARED FILES */}
          <div className="card">
            <h2>Shared</h2>

            {(selectedUser
              ? sharedFiles.filter(
                  (f) =>
                    f.uploader?.toLowerCase() ===
                    selectedUser.toLowerCase()
                )
              : sharedFiles
            ).length === 0 ? (
              <p className="empty">Empty</p>
            ) : (
              <div className="grid">
                {(selectedUser
                  ? sharedFiles.filter(
                      (f) =>
                        f.uploader?.toLowerCase() ===
                        selectedUser.toLowerCase()
                    )
                  : sharedFiles
                ).map((f) => (
                  <div key={f.id} className="file-card">
                    <div>
                      <h4>{f.filename}</h4>
                      <p>
                        {new Date(f.timestamp * 1000).toLocaleString()}
                      </p>
                    </div>

                    <a href={f.ipfs_url} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default App;