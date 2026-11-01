import { useState } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  minLength?: number;
  autoComplete?: string;
};

export default function PasswordField({ value, onChange, required, minLength, autoComplete }: Props) {
  const [show, setShow] = useState(false);
  return (
    <div className="password-field">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
      />
      <button type="button" className="btn" onClick={() => setShow((open) => !open)}>
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}
