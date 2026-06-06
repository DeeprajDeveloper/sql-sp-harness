CREATE PROCEDURE dbo.usp_SimplePayrollUpdate
    @EmployeeID INT,
    @RaiseAmount DECIMAL(18, 2)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @IsSuccess BIT = 0;

    UPDATE dbo.Employees
    SET Salary = Salary + @RaiseAmount,
        LastModified = GETDATE()
    WHERE EmployeeID = @EmployeeID;

    INSERT INTO dbo.AuditLog (EmployeeID, LogMessage, CreatedDate)
    VALUES (@EmployeeID, 'Salary updated', GETDATE());

    SET @IsSuccess = 1;
    SET @IsSuccess = CASE WHEN @@ROWCOUNT > 0 THEN 1 ELSE 0 END;
END
