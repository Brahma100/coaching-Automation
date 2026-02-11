import React from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import TokenGate from '../components/TokenGate.jsx';

function ClassStartToken() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const sessionId = params.sessionId;

  return (
    <TokenGate token={token} sessionId={sessionId} expectedType="class_start">
      {() => (
        <section className="flex min-h-screen items-center justify-center p-6">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center">
            <h2 className="text-2xl font-bold text-slate-900">Class Starting</h2>
            <p className="mt-2 text-sm text-slate-600">You can open attendance now.</p>
            <a
              className="mt-4 inline-flex rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white"
              href={`/attendance/session/${sessionId}?token=${encodeURIComponent(token)}`}
            >
              Open Attendance
            </a>
          </div>
        </section>
      )}
    </TokenGate>
  );
}

export default ClassStartToken;
