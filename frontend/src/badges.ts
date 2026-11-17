export function refreshBadges() {
  window.dispatchEvent(new Event("sbar:badges"));
}
