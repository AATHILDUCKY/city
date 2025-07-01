function getLocationAndSubmit() {
    navigator.geolocation.getCurrentPosition((position) => {
        document.getElementById("lat").value = position.coords.latitude;
        document.getElementById("lng").value = position.coords.longitude;
    }, (error) => {
        alert("Location access denied. Cannot submit complaint.");
    });
}

function initMap(complaints) {
    const map = L.map('map').setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    complaints.forEach(c => {
        const marker = L.marker([c.lat, c.lng]).addTo(map);
        marker.bindPopup(`<b>${c.category}</b><br>${c.desc}<br><img src='/` + c.image + `' width='100'>`);
    });
}