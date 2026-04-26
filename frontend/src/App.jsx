import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

function rupees(paise) {
  return `₹${(paise / 100).toFixed(2)}`;
}

function App() {
  const [merchants, setMerchants] = useState([]);
  const [merchantId, setMerchantId] = useState(1);
  const [accounts, setAccounts] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [message, setMessage] = useState("");

  function requestHeaders(extra = {}) {
    return {
      "Content-Type": "application/json",
      "X-Merchant-Id": String(merchantId),
      ...extra,
    };
  }

  async function load() {
    try {
      const merchantsData = await fetch(`${API}/merchants/`).then(r => r.json());
      setMerchants(merchantsData);

      const accountsData = await fetch(
        `${API}/bank-accounts/?merchant_id=${merchantId}`
      ).then(r => r.json());

      setAccounts(accountsData);

      if (accountsData.length > 0) {
        setBankAccountId(String(accountsData[0].id));
      }

      const dashboardData = await fetch(
        `${API}/dashboard/?merchant_id=${merchantId}`
      ).then(r => r.json());

      setDashboard(dashboardData);
    } catch (err) {
      setMessage(`Load error: ${err.message}`);
    }
  }

  useEffect(() => {
    setBankAccountId("");
    load();

    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [merchantId]);

  async function submit(e) {
    e.preventDefault();
    setMessage("");

    if (!amount || Number(amount) <= 0) {
      alert("Please enter a valid amount");
      return;
    }

    if (!bankAccountId) {
      alert("Please select a bank account");
      return;
    }

    const amountPaise = Math.round(Number(amount) * 100);

    try {
      const res = await fetch(`${API}/payouts/`, {
        method: "POST",
        headers: requestHeaders({
          "Idempotency-Key": crypto.randomUUID(),
        }),
        body: JSON.stringify({
          amount_paise: amountPaise,
          bank_account_id: Number(bankAccountId),
        }),
      });

      const body = await res.json();

      if (res.ok) {
        setMessage(`Payout created successfully: #${body.id}`);
        setAmount("");
        await load();
      } else {
        setMessage(JSON.stringify(body));
      }
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <div className="app">
      <div className="shell">
        <header className="hero">
          <div>
            <p className="eyebrow">Playto Pay</p>
            <h1>Payout Engine Dashboard</h1>
            <p className="subtitle">
              Ledger-based payout system with idempotency, locking, and async processing.
            </p>
          </div>

          <select
            className="merchant-select"
            value={merchantId}
            onChange={e => setMerchantId(Number(e.target.value))}
          >
            {merchants.map(m => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </header>

        {dashboard && (
          <section className="stats">
            <div className="stat-card">
              <p>Available Balance</p>
              <h2>{rupees(dashboard.available_balance_paise)}</h2>
              <span>Ready for withdrawal</span>
            </div>

            <div className="stat-card">
              <p>Held Balance</p>
              <h2>{rupees(dashboard.held_balance_paise)}</h2>
              <span>Reserved for active payouts</span>
            </div>
          </section>
        )}

        <section className="main-grid">
          <form onSubmit={submit} className="panel payout-form">
            <h2>Request Payout</h2>
            <p className="muted">Enter amount in rupees and select bank account.</p>

            <input
              className="input"
              type="number"
              min="1"
              placeholder="Amount in rupees"
              value={amount}
              onChange={e => setAmount(e.target.value)}
            />

            <select
              className="input"
              value={bankAccountId}
              onChange={e => setBankAccountId(e.target.value)}
            >
              <option value="">Select bank account</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>
                  {a.account_holder_name} ••••{a.account_number_last4}
                </option>
              ))}
            </select>

            <button type="submit" className="btn">
              Create Payout
            </button>

            {message && <div className="message">{message}</div>}
          </form>

          <div className="panel">
            <h2>Payout History</h2>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Attempts</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard?.payouts?.map(p => (
                    <tr key={p.id}>
                      <td>#{p.id}</td>
                      <td>{rupees(p.amount_paise)}</td>
                      <td>
                        <span className={`badge ${p.status}`}>
                          {p.status}
                        </span>
                      </td>
                      <td>{p.attempts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {dashboard && (
          <section className="panel">
            <h2>Recent Ledger</h2>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.recent_ledger.map(l => (
                    <tr key={l.id}>
                      <td>#{l.id}</td>
                      <td>
                        <span className={`badge ${l.entry_type}`}>
                          {l.entry_type}
                        </span>
                      </td>
                      <td>{rupees(l.amount_paise)}</td>
                      <td>{l.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);