import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';

function Chart({ title, data, xKey, lines = [], bars = [], height = 280 }) {
  const hasBars = bars.length > 0;

  return (
    <section className="card-panel">
      <h3 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {hasBars ? (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {bars.map((bar) => (
                <Bar key={bar.key} dataKey={bar.key} name={bar.name} fill={bar.color} radius={[6, 6, 0, 0]} />
              ))}
            </BarChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {lines.map((line) => (
                <Line
                  key={line.key}
                  type="monotone"
                  dataKey={line.key}
                  name={line.name}
                  stroke={line.color}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export default Chart;
