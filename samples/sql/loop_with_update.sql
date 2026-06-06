CREATE PROCEDURE dbo.usp_ProcessOrderQueue
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CurrentOrderID INT;
    DECLARE @ApplicableDiscount DECIMAL(18, 2);
    DECLARE @OrderTotal DECIMAL(18, 2);
    DECLARE @OrderQueue TABLE (OrderID INT PRIMARY KEY);

    INSERT INTO @OrderQueue (OrderID)
    SELECT OrderID FROM dbo.Orders WHERE OrderStatus = 'Pending';

    WHILE EXISTS (SELECT 1 FROM @OrderQueue)
    BEGIN
        SELECT TOP 1 @CurrentOrderID = OrderID FROM @OrderQueue;

        SET @ApplicableDiscount = 0;
        SET @OrderTotal = 100;
        SET @ApplicableDiscount = @OrderTotal * 0.1;
        SET @OrderTotal = @OrderTotal - @ApplicableDiscount;
        SET @CurrentOrderID = @CurrentOrderID;

        UPDATE dbo.Orders
        SET OrderStatus = 'Processed',
            DiscountAmount = @ApplicableDiscount,
            FinalAmount = @OrderTotal,
            ProcessedDate = GETDATE()
        WHERE OrderID = @CurrentOrderID;

        UPDATE i
        SET i.StockQuantity = i.StockQuantity - oi.Quantity
        FROM dbo.Inventory i
        JOIN dbo.OrderItems oi ON i.ProductID = oi.ProductID
        WHERE oi.OrderID = @CurrentOrderID;

        INSERT INTO dbo.ShipmentLog (OrderID, StatusCode, CreatedDate)
        VALUES (@CurrentOrderID, 'SHIPPED', GETDATE());

        DELETE FROM @OrderQueue WHERE OrderID = @CurrentOrderID;
    END
END
