import { useEffect, useRef, type ReactNode } from "react";
import { ApiError } from "./api/client";
export function ErrorMessage({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="notice error">
      {error instanceof ApiError
        ? `${error.message} (${error.code})${error.requestId ? ` · Reference ${error.requestId}` : ""}`
        : "Connection failed. Check the local service and retry."}
      {retry && <button onClick={retry}>Retry</button>}
    </div>
  );
}
export function Card({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
export function Dialog({
  title,
  children,
  close,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef(document.activeElement as HTMLElement | null);
  useEffect(() => {
    const previous = opener.current;
    ref.current?.showModal();
    return () => {
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby="dialog-title"
      onKeyDown={(e) => {
        if (e.key !== "Tab") return;
        const controls = [
          ...(ref.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), a[href], [tabindex="0"]',
          ) ?? []),
        ];
        if (!controls.length) {
          e.preventDefault();
          return;
        }
        const first = controls[0],
          last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) close();
      }}
    >
      <h2 id="dialog-title">{title}</h2>
      {children}
      <button disabled={busy} onClick={close}>
        Close
      </button>
    </dialog>
  );
}
