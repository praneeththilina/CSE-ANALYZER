import unittest
from unittest.mock import MagicMock, patch
import stocks

class TestStocksAPI(unittest.TestCase):
    @patch("stocks.get")
    def test_api_company_news(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"news": [{"id": 1, "title": "Test News"}]}
        mock_get.return_value = mock_response

        mock_session = MagicMock()
        symbol = "COMB.N0000"
        res = stocks.api_company_news(mock_session, symbol, news_type="BN", top=False)

        expected_url = "https://www.cse.lk/api/news/web?top=false&type=BN&security=COMB.N0000"
        mock_get.assert_called_once_with(mock_session, expected_url)
        self.assertEqual(res, {"news": [{"id": 1, "title": "Test News"}]})

    @patch("stocks.get")
    def test_api_company_news_top(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"news": []}
        mock_get.return_value = mock_response

        mock_session = MagicMock()
        symbol = "JKH.N0000"
        res = stocks.api_company_news(mock_session, symbol, news_type="ANN", top=True)

        expected_url = "https://www.cse.lk/api/news/web?top=true&type=ANN&security=JKH.N0000"
        mock_get.assert_called_once_with(mock_session, expected_url)
        self.assertEqual(res, {"news": []})

if __name__ == "__main__":
    unittest.main()
