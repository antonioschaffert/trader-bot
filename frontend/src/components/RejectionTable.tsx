import { useState } from "react";
import type { RejectionsResponse } from "@/lib/api";
import { formatDateTimeET } from "@/lib/time";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  data: RejectionsResponse | null;
  onFilterChange: (symbol: string, strategy: string) => void;
  symbols: string[];
}

const STRATEGIES = ["swing", "exhaustion"];

export function RejectionTable({ data, onFilterChange, symbols }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState("");

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSymbolChange = (value: string | null) => {
    const v = !value || value === "__all__" ? "" : value;
    setSelectedSymbol(v);
    onFilterChange(v, selectedStrategy);
  };

  const handleStrategyChange = (value: string | null) => {
    const v = !value || value === "__all__" ? "" : value;
    setSelectedStrategy(v);
    onFilterChange(selectedSymbol, v);
  };

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Scan Rejections</h2>
        <div className="flex items-center gap-2">
          <Select
            value={selectedSymbol || "__all__"}
            onValueChange={handleSymbolChange}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Symbols</SelectItem>
              {symbols.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={selectedStrategy || "__all__"}
            onValueChange={handleStrategyChange}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Strategies</SelectItem>
              {STRATEGIES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!data ? (
        <Skeleton className="h-48 w-full rounded-xl" />
      ) : data.items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No rejections found.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Symbol</TableHead>
              <TableHead>Strategy</TableHead>
              <TableHead>Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.flatMap((scan) =>
              scan.rejections.map((rej, ri) => {
                const rowId = `${scan._id}-${ri}`;
                const isExpanded = expanded.has(rowId);
                return [
                  <TableRow
                    key={rowId}
                    className="cursor-pointer"
                    onClick={() => toggleExpanded(rowId)}
                  >
                    <TableCell className="text-xs">
                      {formatDateTimeET(scan.timestamp)}
                    </TableCell>
                    <TableCell className="font-medium">
                      {scan.symbol}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{rej.strategy}</Badge>
                    </TableCell>
                    <TableCell>{rej.reason}</TableCell>
                  </TableRow>,
                  isExpanded ? (
                    <TableRow key={`${rowId}-detail`}>
                      <TableCell colSpan={4}>
                        <pre className="max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">
                          {JSON.stringify(rej.variables, null, 2)}
                        </pre>
                      </TableCell>
                    </TableRow>
                  ) : null,
                ];
              }),
            )}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
