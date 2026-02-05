const btn = document.getElementById("sendBtn");
const output = document.getElementById("output");

btn.addEventListener("click", async () => {
  output.textContent = "Kjører...";
  const valueInput = document.getElementById("value").value;

  try {
    const res = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: Number(valueInput) })
    });
    const data = await res.json();

    if (!data.ok) {
      output.textContent = `Feil: ${data.error || "Ukjent feil"}`;
    } else {
      output.textContent = `Resultat: ${data.result}`;
    }
  } catch (err) {
    output.textContent = `Nettverksfeil: ${err.message}`;
  }
});
