"use client";

import { useEffect, useState } from "react";

interface TargetItem {
  market_hash_name: string;
  max_buy_price: number;
  max_float?: number | null;
  min_float?: number | null;
}

interface StatusResponse {
  status: string;
  active_targets: number;
  total_deals: number;
  targets: TargetItem[];
}

interface DealItem {
  listing_id: string;
  market_hash_name: string;
  price: number;
  max_buy_price: number;
  net_profit: number;
  net_profit_margin_pct?: number;
  float_value: number | null;
  buy_url: string;
  detected_at: string;
}

const API_BASE = "http://127.0.0.1:8000/api/v1";
const POLL_INTERVAL_MS = 2000;

function formatTimestamp(isoString: string | null): string {
  if (!isoString) return "--:--:--";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleTimeString("en-GB", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatFloatLimit(target: TargetItem): string {
  const hasMin = typeof target.min_float === "number";
  const hasMax = typeof target.max_float === "number";
  if (hasMin && hasMax) {
    return `${target.min_float!.toFixed(4)} - ${target.max_float!.toFixed(4)}`;
  }
  if (hasMax) {
    return `<= ${target.max_float!.toFixed(4)}`;
  }
  if (hasMin) {
    return `>= ${target.min_float!.toFixed(4)}`;
  }
  return "ANY";
}

export default function SniperDashboardPage() {
  const [online, setOnline] = useState<boolean>(false);
  const [statusData, setStatusData] = useState<StatusResponse | null>(null);
  const [deals, setDeals] = useState<DealItem[]>([]);
  const [lastPoll, setLastPoll] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function pollTelemetry() {
      try {
        const [statusRes, dealsRes] = await Promise.all([
          fetch(`${API_BASE}/status`, { cache: "no-store" }),
          fetch(`${API_BASE}/deals`, { cache: "no-store" }),
        ]);

        if (!isMounted) return;

        if (statusRes.ok && dealsRes.ok) {
          const statusJson: StatusResponse = await statusRes.json();
          const dealsJson: DealItem[] = await dealsRes.json();

          setStatusData(statusJson);
          setDeals(Array.isArray(dealsJson) ? dealsJson : []);
          setOnline(statusJson.status === "online" || statusJson.status === "running");
          setLastPoll(new Date().toISOString());
        } else {
          setOnline(false);
          setLastPoll(new Date().toISOString());
        }
      } catch {
        if (!isMounted) return;
        setOnline(false);
        setLastPoll(new Date().toISOString());
      }
    }

    pollTelemetry();
    const intervalId = setInterval(pollTelemetry, POLL_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  const targets = statusData?.targets ?? [];
  const activeTargetsCount = statusData?.active_targets ?? targets.length;
  const dealsFoundCount = statusData?.total_deals ?? deals.length;

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa] font-sans antialiased selection:bg-[#27272a] selection:text-[#fafafa]">
      {/* 1. TOP TELEMETRY BAR */}
      <header className="w-full bg-[#18181b] border-b border-[#27272a] px-4 py-2">
        <div className="max-w-[1600px] mx-auto flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-6">
            <span className="font-mono font-bold tracking-wider text-[#fafafa] uppercase">
              CS2 // SNIPER.EXEC
            </span>
            <div className="flex items-center gap-2 border-l border-[#27272a] pl-6">
              <span className="text-[#71717a] uppercase tracking-wider">SYS.STATUS</span>
              <span
                className={`inline-block h-2 w-2 ${
                  online ? "bg-[#10b981]" : "bg-[#71717a]"
                }`}
              />
              <span
                className={`font-mono tabular-nums font-semibold uppercase ${
                  online ? "text-[#10b981]" : "text-[#71717a]"
                }`}
              >
                {online ? "ONLINE" : "OFFLINE"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-6 font-mono tabular-nums">
            <div className="flex items-center gap-2">
              <span className="font-sans text-[#71717a] uppercase tracking-wider">
                ACTIVE TARGETS
              </span>
              <span className="text-[#fafafa] font-semibold">{activeTargetsCount}</span>
            </div>

            <div className="flex items-center gap-2 border-l border-[#27272a] pl-6">
              <span className="font-sans text-[#71717a] uppercase tracking-wider">
                DEALS FOUND
              </span>
              <span
                className={`font-semibold ${
                  dealsFoundCount > 0 ? "text-[#10b981]" : "text-[#fafafa]"
                }`}
              >
                {dealsFoundCount}
              </span>
            </div>

            <div className="flex items-center gap-2 border-l border-[#27272a] pl-6">
              <span className="font-sans text-[#71717a] uppercase tracking-wider">
                LAST POLL
              </span>
              <span className="text-[#fafafa]">{formatTimestamp(lastPoll)}</span>
            </div>
          </div>
        </div>
      </header>

      {/* MAIN WORKSPACE */}
      <main className="max-w-[1600px] mx-auto p-4 flex flex-col gap-4">
        {/* 2. MONITORED TARGETS STRIP / TABLE */}
        <section className="border border-[#27272a] bg-[#18181b]">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#27272a] bg-[#09090b]">
            <h2 className="text-[11px] font-mono uppercase tracking-widest text-[#71717a]">
              MONITORED TARGETS (MEMORY_DB)
            </h2>
            <span className="text-[11px] font-mono tabular-nums text-[#71717a]">
              COUNT: {targets.length}
            </span>
          </div>

          {targets.length === 0 ? (
            <div className="px-3 py-3 text-xs font-mono text-[#71717a]">
              {online
                ? "NO ACTIVE TARGETS LOADED IN MEMORY_DB."
                : "BACKEND OFFLINE — AWAITING TELEMETRY STREAM (127.0.0.1:8000)..."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-[#27272a] text-[11px] text-[#71717a] uppercase font-mono">
                    <th className="py-1.5 px-3 font-normal">ITEM (MARKET_HASH_NAME)</th>
                    <th className="py-1.5 px-3 font-normal text-right w-44">MAX BUY ($)</th>
                    <th className="py-1.5 px-3 font-normal text-right w-44">FLOAT LIMIT</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#27272a]">
                  {targets.map((target) => (
                    <tr
                      key={target.market_hash_name}
                      className="bg-[#18181b] hover:bg-[#09090b]"
                    >
                      <td className="py-1.5 px-3 font-medium text-[#fafafa]">
                        {target.market_hash_name}
                      </td>
                      <td className="py-1.5 px-3 font-mono tabular-nums text-right text-[#fafafa]">
                        ${Number(target.max_buy_price).toFixed(2)}
                      </td>
                      <td className="py-1.5 px-3 font-mono tabular-nums text-right text-[#71717a]">
                        {formatFloatLimit(target)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* 3. LIVE DEALS TABLE */}
        <section className="border border-[#27272a] bg-[#18181b]">
          <div className="flex items-center justify-between px-3 py-2 border-b border-[#27272a] bg-[#09090b]">
            <h2 className="text-[11px] font-mono uppercase tracking-widest text-[#71717a]">
              LIVE ARBITRAGE FEED // CSFLOAT_BUY_NOW
            </h2>
            <span className="text-[11px] font-mono tabular-nums text-[#71717a]">
              POLL: 2.0s | CAP: 50
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-[#27272a] bg-[#09090b] text-[11px] text-[#71717a] uppercase font-mono">
                  <th className="py-2 px-3 font-normal w-28">TIME</th>
                  <th className="py-2 px-3 font-normal">ITEM NAME</th>
                  <th className="py-2 px-3 font-normal text-right w-36">FLOAT</th>
                  <th className="py-2 px-3 font-normal text-right w-36">BUY PRICE ($)</th>
                  <th className="py-2 px-3 font-normal text-right w-48">NET PROFIT ($ / %)</th>
                  <th className="py-2 px-3 font-normal text-right w-28">EXEC</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#27272a]">
                {deals.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="py-8 px-3 text-center font-mono text-xs text-[#71717a]"
                    >
                      {online
                        ? "SCANNING LIVE LISTINGS — NO POSITIVE-MARGIN DEALS DETECTED YET."
                        : "FEED DISCONNECTED — VERIFY FASTAPI ENGINE AT 127.0.0.1:8000."}
                    </td>
                  </tr>
                ) : (
                  deals.map((deal) => {
                    const price = Number(deal.price) || 0;
                    const netProfit = Number(deal.net_profit) || 0;
                    const pct =
                      typeof deal.net_profit_margin_pct === "number"
                        ? deal.net_profit_margin_pct
                        : price > 0
                        ? (netProfit / price) * 100
                        : 0;

                    return (
                      <tr
                        key={`${deal.listing_id}-${deal.detected_at}`}
                        className="bg-[#18181b] hover:bg-[#09090b]"
                      >
                        <td className="py-2 px-3 font-mono tabular-nums text-[#71717a] whitespace-nowrap">
                          {formatTimestamp(deal.detected_at)}
                        </td>
                        <td className="py-2 px-3 font-medium text-[#fafafa]">
                          <div className="flex items-center justify-between gap-2">
                            <span>{deal.market_hash_name}</span>
                            <span className="font-mono tabular-nums text-[11px] text-[#71717a]">
                              #{deal.listing_id}
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-3 font-mono tabular-nums text-right text-[#fafafa]">
                          {typeof deal.float_value === "number"
                            ? deal.float_value.toFixed(6)
                            : "N/A"}
                        </td>
                        <td className="py-2 px-3 font-mono tabular-nums text-right text-[#fafafa]">
                          ${price.toFixed(2)}
                        </td>
                        <td className="py-2 px-3 font-mono tabular-nums text-right font-semibold text-[#10b981] whitespace-nowrap">
                          +${netProfit.toFixed(2)} (+{pct.toFixed(2)}%)
                        </td>
                        <td className="py-1.5 px-3 text-right whitespace-nowrap">
                          <a
                            href={deal.buy_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block border border-[#fafafa] bg-[#fafafa] text-[#09090b] hover:bg-[#09090b] hover:text-[#fafafa] font-mono text-[11px] font-bold px-2.5 py-1 tracking-tight"
                          >
                            {"BUY ->"}
                          </a>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
