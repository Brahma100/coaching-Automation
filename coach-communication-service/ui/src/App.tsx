import { useMemo, useState } from "react";

type Section = "Providers" | "Automation Rules" | "Templates" | "Broadcast" | "Delivery Logs" | "Analytics";

const nav: Section[] = ["Providers", "Automation Rules", "Templates", "Broadcast", "Delivery Logs", "Analytics"];

export function App() {
  const [active, setActive] = useState<Section>("Providers");

  const panel = useMemo(() => {
    if (active === "Providers") {
      return (
        <>
          <h2>Connect Providers</h2>
          <div className="grid two">
            <Card title="Telegram" status="Connected">
              <label>Bot token</label>
              <input placeholder="12345:ABCDEF" />
              <button>Test connection</button>
            </Card>
            <Card title="WhatsApp" status="Error">
              <label>Phone number ID</label>
              <input placeholder="123456789" />
              <label>Access token</label>
              <input placeholder="EAAB..." />
              <label>Webhook verify token</label>
              <input placeholder="verify-token" />
              <button>Test connection</button>
            </Card>
          </div>
        </>
      );
    }
    if (active === "Automation Rules") {
      return (
        <>
          <h2>Automation Rules</h2>
          <div className="card list">
            {[
              "Send attendance alerts",
              "Notify parents",
              "Batch CRUD alerts",
              "Fee reminders",
              "Daily brief",
              "Homework alerts"
            ].map((label) => (
              <label key={label} className="toggle">
                <input type="checkbox" defaultChecked />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </>
      );
    }
    if (active === "Templates") {
      return (
        <>
          <h2>Template Editor</h2>
          <div className="grid two">
            <div className="card">
              <label>Message body</label>
              <textarea defaultValue={"Hello {{student_name}}\nBatch {{batch}} moved to {{time}}"} />
              <small>Variables: student_name, batch, time</small>
            </div>
            <div className="card">
              <h3>Live Preview</h3>
              <p>Hello Riya</p>
              <p>Batch A moved to 5:00 PM</p>
            </div>
          </div>
        </>
      );
    }
    if (active === "Broadcast") {
      return (
        <>
          <h2>Broadcast</h2>
          <div className="card">
            <label>Audience</label>
            <input placeholder="parents.batch.a" />
            <label>Message</label>
            <textarea placeholder="Type announcement" />
            <button>Queue Broadcast</button>
          </div>
        </>
      );
    }
    if (active === "Delivery Logs") {
      return (
        <>
          <h2>Delivery Logs</h2>
          <div className="card table">
            <div>attendance.submitted | telegram | delivered</div>
            <div>fee.reminder | whatsapp | retrying</div>
            <div>batch.rescheduled | telegram->whatsapp | delivered</div>
          </div>
        </>
      );
    }
    return (
      <>
        <h2>Analytics</h2>
        <div className="grid three">
          <Card title="Delivery Success">96.4%</Card>
          <Card title="Daily Volume">1,243</Card>
          <Card title="Provider Comparison">TG 58% | WA 42%</Card>
        </div>
      </>
    );
  }, [active]);

  return (
    <div className="layout">
      <aside>
        <h1>Communication</h1>
        <nav>
          {nav.map((item) => (
            <button key={item} onClick={() => setActive(item)} className={active === item ? "active" : ""}>
              {item}
            </button>
          ))}
        </nav>
      </aside>
      <main>{panel}</main>
    </div>
  );
}

function Card({
  title,
  children,
  status
}: {
  title: string;
  children: React.ReactNode;
  status?: string;
}) {
  return (
    <section className="card">
      <header>
        <h3>{title}</h3>
        {status ? <span className={status === "Connected" ? "ok" : "warn"}>{status}</span> : null}
      </header>
      {children}
    </section>
  );
}
