// mock_api.js
class AnalyticsMockAPI {
    constructor() {
        this.baseData = {
            annualSales: { 
                labels: ['2008', '2009'], 
                data: [10835700, 5613000] 
            },
            monthlyReturn: { 
                labels: ['2009/1','2009/2','2009/3','2009/4','2009/5','2009/6','2009/7'], 
                data: [0.87, 0.79, 0.82, 0.81, 0.83, 0.65, null] 
            },
            orders: { 
                labels: ['Annasu', 'Bob', 'Andrew', 'Evelyn', 'Susan', 'Margaret', 'Nancy'], 
                data: [20.51, 17.95, 15.38, 12.82, 12.82, 10.26, 10.26] 
            },
            ranking: { 
                labels: ['Annasu','Bob','Evelyn','Susan','Andrew','Nancy','Tom','Anna','Margaret','Eve','Steven','Janet','Happy','Robert','Fanny','Michael','Selina','Rechia','Sheep','Jackie','Geoge','White','Sky','Zero'],
                data: [500000, 490000, 420000, 420000, 400000, 300000, 290000, 280000, 280000, 250000, 240000, 230000, 220000, 180000, 170000, 150000, 140000, 130000, 100000, 100000, 90000, 70000, 60000, 60000]
            }
        };
    }
    // Return base data but can simulate motion if needed later
    async getDashboardData() {
        return new Promise((resolve) => {
            setTimeout(() => resolve(this.baseData), 200);
        });
    }
}
window.AnalyticsAPI = new AnalyticsMockAPI();
